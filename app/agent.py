import os
import json
from dotenv import load_dotenv
from groq import Groq
from app import paypal, db

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
DEFAULT_CLIENT_EMAIL = os.getenv("DEMO_CLIENT_EMAIL")

SYSTEM_PROMPT = (
    "You are a billing assistant for a freelancer. When the freelancer describes "
    "completed work, call create_invoice with the details. Infer a short professional "
    "line-item description. Use ISO currency codes (INR for ₹, USD for $). "
    "If the amount or client is missing, ask a short clarifying question instead of guessing."
)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "create_invoice",
        "description": "Prepare an invoice for a client after completed work.",
        "parameters": {
            "type": "object",
            "properties": {
                "client_name": {"type": "string"},
                "description": {"type": "string", "description": "Short line-item description"},
                "amount": {"type": "number"},
                "currency": {"type": "string", "description": "ISO code, e.g. INR or USD"},
                "due_in_days": {"type": "integer", "description": "Payment terms in days, default 14"},
            },
            "required": ["client_name", "description", "amount", "currency"],
        },
    },
}]


def propose_invoice(user_input) -> dict:
    """Turn a message (or a chat history) into an invoice PROPOSAL. Nothing is sent to PayPal here."""
    history = [{"role": "user", "content": user_input}] if isinstance(user_input, str) else user_input
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *history],
        tools=TOOLS,
        tool_choice="auto",
    )
    msg = resp.choices[0].message
    if not msg.tool_calls:
        return {"type": "message", "text": msg.content}

    args = json.loads(msg.tool_calls[0].function.arguments)
    try:
        args["amount"] = float(args["amount"])
        args["currency"] = args.get("currency", "USD").upper()
        args["due_in_days"] = int(args.get("due_in_days") or 14)
        args["usd_amount"] = paypal.to_usd(args["amount"], args["currency"])
    except (ValueError, KeyError, paypal.PayPalError) as e:
        return {"type": "message", "text": f"I couldn't prepare that invoice: {e}"}

    args["client_email"] = DEFAULT_CLIENT_EMAIL
    return {"type": "proposal", "invoice": args}


def approve_and_send(proposal: dict) -> dict:
    """Called ONLY after the freelancer approves. Creates, sends and records the invoice."""
    inv = proposal["invoice"]
    created = paypal.create_invoice(
        client_name=inv["client_name"],
        client_email=inv["client_email"],
        description=inv["description"],
        amount=inv["amount"],
        currency=inv["currency"],
        due_in_days=inv["due_in_days"],
    )
    paypal.send_invoice(created["invoice_id"], subject=f"Invoice from your freelancer: {inv['description'][:60]}")
    info = paypal.get_invoice(created["invoice_id"])

    db.save_invoice({
        "invoice_id": created["invoice_id"],
        "invoice_number": created["invoice_number"],
        "client_name": inv["client_name"],
        "client_email": inv["client_email"],
        "description": inv["description"],
        "amount": inv["amount"],
        "currency": inv["currency"],
        "usd_amount": created["usd_amount"],
        "status": info["status"],
        "due_date": info["due_date"],
        "pay_url": info["pay_url"],
    })
    return {"invoice_id": created["invoice_id"], "status": info["status"], "pay_url": info["pay_url"]}