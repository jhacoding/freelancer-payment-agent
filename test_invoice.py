import os
import sys
from app.paypal import create_invoice, send_invoice, get_invoice

if len(sys.argv) > 1:
    # python test_invoice.py INV2-XXXX  -> just check status
    info = get_invoice(sys.argv[1])
    print("Status:", info["status"])
    print("Pay URL:", info["pay_url"])
else:
    inv = create_invoice(
        client_name="ABC",
        client_email=os.getenv("DEMO_CLIENT_EMAIL"),
        description="Website project",
        amount=40000,
        currency="INR",
        due_in_days=14,
    )
    print("Created:", inv)
    send_invoice(inv["invoice_id"], subject="Invoice for your website project")
    info = get_invoice(inv["invoice_id"])
    print("Status:", info["status"])
    print("Pay URL:", info["pay_url"])