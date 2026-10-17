import os
import time
import requests
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
INR_PER_USD = float(os.getenv("INR_PER_USD", "88"))

_token = {"value": None, "expires_at": 0}


class PayPalError(Exception):
    pass


def get_access_token() -> str:
    """Fetch an OAuth token, cached until shortly before it expires."""
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    r = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if r.status_code != 200:
        raise PayPalError(f"Auth failed: {r.status_code} {r.text}")
    data = r.json()
    _token["value"] = data["access_token"]
    _token["expires_at"] = time.time() + data.get("expires_in", 3000)
    return _token["value"]


def _request(method: str, path: str, **kwargs) -> dict:
    headers = {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }
    r = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=30, **kwargs)
    if not r.ok:
        raise PayPalError(f"{method} {path} -> {r.status_code}: {r.text}")
    return r.json() if r.content else {}


def to_usd(amount: float, currency: str) -> float:
    currency = currency.upper()
    if currency == "USD":
        return round(amount, 2)
    if currency == "INR":
        return round(amount / INR_PER_USD, 2)
    raise PayPalError(f"Unsupported currency for demo: {currency}")


def create_invoice(client_name, client_email, description, amount,
                   currency="USD", due_in_days=14) -> dict:
    """Create a draft invoice. Returns its id, number and USD amount."""
    usd_amount = to_usd(amount, currency)
    number = _request("POST", "/v2/invoicing/generate-next-invoice-number")["invoice_number"]

    note = "Thank you for your business."
    if currency.upper() != "USD":
        note = (f"Original amount: {currency.upper()} {amount:,.2f} "
                f"(billed in USD at 1 USD = {INR_PER_USD} INR). " + note)

    body = {
        "detail": {
            "invoice_number": number,
            "invoice_date": date.today().isoformat(),
            "currency_code": "USD",
            "note": note,
            "payment_term": {
                "term_type": "DUE_ON_DATE_SPECIFIED",
                "due_date": (date.today() + timedelta(days=due_in_days)).isoformat(),
            },
        },
        "primary_recipients": [{
            "billing_info": {
                "business_name": client_name,
                "email_address": client_email,
            }
        }],
        "items": [{
            "name": description[:200],
            "quantity": "1",
            "unit_amount": {"currency_code": "USD", "value": f"{usd_amount:.2f}"},
        }],
    }
    result = _request("POST", "/v2/invoicing/invoices", json=body)
    invoice_id = result["href"].rstrip("/").split("/")[-1]
    return {"invoice_id": invoice_id, "invoice_number": number, "usd_amount": usd_amount}


def send_invoice(invoice_id: str, subject=None, note=None) -> dict:
    body = {"send_to_recipient": True, "send_to_invoicer": False}
    if subject:
        body["subject"] = subject
    if note:
        body["note"] = note
    return _request("POST", f"/v2/invoicing/invoices/{invoice_id}/send", json=body)


def get_invoice(invoice_id: str) -> dict:
    """Return status plus the link the client uses to pay."""
    data = _request("GET", f"/v2/invoicing/invoices/{invoice_id}")
    return {
        "invoice_id": invoice_id,
        "status": data.get("status"),
        "due_date": data.get("detail", {}).get("payment_term", {}).get("due_date"),
        "pay_url": data.get("detail", {}).get("metadata", {}).get("recipient_view_url"),
        "raw": data,
    }


def send_reminder(invoice_id: str, subject: str, note: str) -> dict:
    body = {"subject": subject, "note": note, "send_to_invoicer": False}
    return _request("POST", f"/v2/invoicing/invoices/{invoice_id}/remind", json=body)