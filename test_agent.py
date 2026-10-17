from app import db
from app.agent import propose_invoice, approve_and_send

db.init_db()

text = input("Freelancer: ")
result = propose_invoice(text)

if result["type"] == "message":
    print("\nAI:", result["text"])
else:
    inv = result["invoice"]
    print("\n--- Invoice preview ---")
    print(f"Client:      {inv['client_name']} <{inv['client_email']}>")
    print(f"Work:        {inv['description']}")
    print(f"Amount:      {inv['currency']} {inv['amount']:,.2f}  (≈ USD {inv['usd_amount']})")
    print(f"Due in:      {inv['due_in_days']} days")
    if input("\nApprove and send? (y/n): ").strip().lower() == "y":
        out = approve_and_send(result)
        print("\nSent!", out)
    else:
        print("Cancelled. Nothing was sent.")