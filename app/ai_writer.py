import os
import json
from datetime import date, datetime
from dotenv import load_dotenv
from groq import Groq
from app import db, paypal
from app.sync import CLOSED_STATUSES, PAID_STATUSES

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


def _chat(system: str, user: str, json_mode: bool = False) -> str:
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.4,
        **kwargs,
    )
    return resp.choices[0].message.content.strip()


# ---------- Overdue detection (plain Python, no AI) ----------

def days_overdue(row: dict) -> int:
    if row["status"] in CLOSED_STATUSES or not row.get("due_date"):
        return 0
    return max(0, (date.today() - date.fromisoformat(row["due_date"])).days)


def overdue_invoices() -> list[dict]:
    return [r for r in db.list_invoices() if days_overdue(r) > 0]


def tone_for(days: int, reminders_sent: int) -> str:
    if days <= 7 and reminders_sent == 0:
        return "friendly and light, assume it was simply forgotten"
    if days <= 21:
        return "polite but firm, clearly state the invoice is overdue and ask for a payment date"
    return "formal final notice: professional, serious, no threats and no legal claims"


# ---------- AI reminder ----------

def write_reminder(row: dict) -> dict:
    days = days_overdue(row)
    tone = tone_for(days, row["reminders_sent"])
    system = (
        "You write short payment reminder emails for a freelancer to send to a client. "
        "Never invent late fees, deadlines, legal action or facts not given. "
        "Do not include a signature name or a payment link (the invoice system adds the link). "
        'Reply ONLY with JSON: {"subject": "...", "note": "..."}. '
        "The note must be under 90 words."
    )
    user = (
        f"Client: {row['client_name']}\n"
        f"Invoice number: {row['invoice_number']}\n"
        f"Work: {row['description']}\n"
        f"Amount: {row['currency']} {row['amount']:,.2f} (billed as USD {row['usd_amount']})\n"
        f"Days overdue: {days}\n"
        f"Reminders already sent: {row['reminders_sent']}\n"
        f"Tone: {tone}"
    )
    raw = _chat(system, user, json_mode=True)
    try:
        data = json.loads(raw)
        return {"subject": data["subject"][:200], "note": data["note"][:1000], "tone": tone, "days": days}
    except (json.JSONDecodeError, KeyError):
        return {
            "subject": f"Reminder: invoice {row['invoice_number']} is overdue",
            "note": f"Hi {row['client_name']}, this is a reminder that your invoice is {days} days overdue. Please arrange payment.",
            "tone": tone,
            "days": days,
        }


def send_reminder_for(row: dict, draft: dict):
    """Call only after the freelancer approves the draft."""
    paypal.send_reminder(row["invoice_id"], draft["subject"], draft["note"])
    db.increment_reminders(row["invoice_id"])


# ---------- Payment confirmation ----------

def payment_confirmation(row: dict) -> str:
    return _chat(
        "You are a freelancer's billing assistant. Write ONE or TWO friendly sentences telling the freelancer a payment arrived.",
        f"Client {row['client_name']} paid invoice {row['invoice_number']} for "
        f"{row['currency']} {row['amount']:,.2f} (USD {row['usd_amount']}).",
    )


# ---------- Monthly summary ----------

def compute_month_stats(month: str | None = None) -> dict:
    """month = 'YYYY-MM'. The numbers are computed here, never by the AI."""
    month = month or date.today().strftime("%Y-%m")
    rows = db.list_invoices()

    paid = [r for r in rows if r["status"] in PAID_STATUSES and (r["paid_at"] or "").startswith(month)]
    open_rows = [r for r in rows if r["status"] not in CLOSED_STATUSES]

    days_to_pay = []
    for r in paid:
        created = datetime.fromisoformat(r["created_at"])
        paid_at = datetime.fromisoformat(r["paid_at"])
        days_to_pay.append((paid_at - created).total_seconds() / 86400)

    return {
        "month": month,
        "paid_count": len(paid),
        "paid_total_usd": round(sum(r["usd_amount"] for r in paid), 2),
        "paid_total_inr_equivalent": round(sum(r["amount"] for r in paid if r["currency"] == "INR"), 2),
        "outstanding_count": len(open_rows),
        "outstanding_total_usd": round(sum(r["usd_amount"] for r in open_rows), 2),
        "overdue": [
            {"client": r["client_name"], "days_overdue": days_overdue(r), "usd": r["usd_amount"]}
            for r in open_rows if days_overdue(r) > 0
        ],
        "avg_days_to_get_paid": round(sum(days_to_pay) / len(days_to_pay), 1) if days_to_pay else None,
        "top_clients": sorted(
            {r["client_name"]: 0 for r in paid}.keys(),
            key=lambda c: -sum(r["usd_amount"] for r in paid if r["client_name"] == c),
        )[:3],
    }


def monthly_summary(month: str | None = None) -> str:
    stats = compute_month_stats(month)
    system = (
        "You are a friendly financial assistant for a freelancer. Write a 4 to 6 sentence summary of their month "
        "in natural, conversational language, using ONLY the numbers provided. Do not do your own arithmetic "
        "or invent figures. Skip fields that are empty or null instead of mentioning them. "
        "If nothing has been paid yet, say so plainly. "
        "End with one practical suggestion (for example, which overdue client to follow up with first)."
    )
    return _chat(system, json.dumps(stats))