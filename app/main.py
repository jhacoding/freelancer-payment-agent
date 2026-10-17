import uuid
from datetime import date, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app import db, agent, ai_writer, paypal
from app.sync import sync_all, PAID_STATUSES

BASE_DIR = Path(__file__).resolve().parent.parent
app = FastAPI(title="AI Freelancer Payment Agent")
db.init_db()

PROPOSALS: dict[str, dict] = {}   # proposal_id -> proposal
DRAFTS: dict[str, tuple] = {}     # draft_id -> (invoice_id, draft)


class Msg(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    history: list[Msg]


class OverdueIn(BaseModel):
    days: int = 10


@app.get("/")
def home():
    return FileResponse(BASE_DIR / "static" / "index.html")


# ---------- Chat and approval ----------

@app.post("/api/chat")
def chat(body: ChatIn):
    history = [m.model_dump() for m in body.history if m.role in ("user", "assistant")][-12:]
    if not history or history[-1]["role"] != "user":
        raise HTTPException(400, "Send a message first.")
    try:
        result = agent.propose_invoice(history)
    except Exception as e:
        raise HTTPException(502, f"AI error: {e}")
    if result["type"] == "proposal":
        pid = uuid.uuid4().hex
        PROPOSALS[pid] = result
        return {"type": "proposal", "proposal_id": pid, "invoice": result["invoice"]}
    return result


@app.post("/api/proposals/{pid}/approve")
def approve(pid: str):
    proposal = PROPOSALS.pop(pid, None)
    if not proposal:
        raise HTTPException(404, "Proposal expired or already used.")
    try:
        return agent.approve_and_send(proposal)
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))


@app.post("/api/proposals/{pid}/cancel")
def cancel(pid: str):
    PROPOSALS.pop(pid, None)
    return {"ok": True}


# ---------- Invoices, sync, reminders ----------

@app.get("/api/invoices")
def invoices():
    rows = db.list_invoices()
    for r in rows:
        r["days_overdue"] = ai_writer.days_overdue(r)
    return rows


@app.post("/api/sync")
def sync():
    try:
        newly_paid = sync_all()
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    return [{"invoice_number": r["invoice_number"],
             "client_name": r["client_name"],
             "message": ai_writer.payment_confirmation(r)} for r in newly_paid]


@app.post("/api/invoices/{invoice_id}/simulate-overdue")
def simulate_overdue(invoice_id: str, body: OverdueIn):
    if not db.get_invoice_row(invoice_id):
        raise HTTPException(404, "Invoice not found.")
    days = max(1, min(body.days, 365))
    db.set_due_date(invoice_id, (date.today() - timedelta(days=days)).isoformat())
    return {"ok": True}


@app.post("/api/invoices/{invoice_id}/reminder-draft")
def reminder_draft(invoice_id: str):
    row = db.get_invoice_row(invoice_id)
    if not row:
        raise HTTPException(404, "Invoice not found.")
    if ai_writer.days_overdue(row) == 0:
        raise HTTPException(400, "This invoice is not overdue.")
    draft = ai_writer.write_reminder(row)
    did = uuid.uuid4().hex
    DRAFTS[did] = (invoice_id, draft)
    return {"draft_id": did, **draft}


@app.post("/api/reminders/{did}/send")
def reminder_send(did: str):
    item = DRAFTS.pop(did, None)
    if not item:
        raise HTTPException(404, "Draft expired or already used.")
    invoice_id, draft = item
    try:
        ai_writer.send_reminder_for(db.get_invoice_row(invoice_id), draft)
    except paypal.PayPalError as e:
        raise HTTPException(502, str(e))
    return {"ok": True}


# ---------- Earnings ----------

@app.get("/api/stats")
def stats():
    return ai_writer.compute_month_stats()


@app.get("/api/earnings")
def earnings():
    totals: dict[str, float] = {}
    for r in db.list_invoices():
        if r["status"] in PAID_STATUSES and r["paid_at"]:
            month = r["paid_at"][:7]
            totals[month] = round(totals.get(month, 0) + r["usd_amount"], 2)
    return dict(sorted(totals.items()))


@app.get("/api/summary")
def summary():
    return {"text": ai_writer.monthly_summary()}