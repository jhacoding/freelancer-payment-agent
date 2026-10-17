from datetime import date, timedelta
from app import db
from app.sync import sync_all
from app import ai_writer

db.init_db()

MENU = """
1) Sync payments from PayPal
2) Simulate an invoice becoming overdue (demo)
3) Draft and send AI reminders for overdue invoices
4) Monthly earnings summary
5) List invoices
q) Quit
"""

while True:
    print(MENU)
    choice = input("> ").strip().lower()

    if choice == "1":
        newly_paid = sync_all()
        if not newly_paid:
            print("No new payments.")
        for row in newly_paid:
            print("PAID:", ai_writer.payment_confirmation(row))

    elif choice == "2":
        rows = [r for r in db.list_invoices() if r["status"] not in ("PAID", "MARKED_AS_PAID", "CANCELLED")]
        if not rows:
            print("No open invoices.")
        else:
            for i, r in enumerate(rows, start=1):
                print(f"{i}) Invoice {r['invoice_number']} - {r['client_name']} ${r['usd_amount']} due {r['due_date']}")
            try:
                idx = int(input("Pick the number in front of the invoice (1, 2, ...): ")) - 1
                days = int(input("Make it how many days overdue? "))
                db.set_due_date(rows[idx]["invoice_id"], (date.today() - timedelta(days=days)).isoformat())
                print("Done.")
            except (ValueError, IndexError):
                print("Invalid choice, try again.")

    elif choice == "3":
        overdue = ai_writer.overdue_invoices()
        if not overdue:
            print("Nothing overdue.")
        for row in overdue:
            draft = ai_writer.write_reminder(row)
            print(f"\n--- Reminder for {row['client_name']} ({draft['days']} days overdue, tone: {draft['tone']}) ---")
            print("Subject:", draft["subject"])
            print(draft["note"])
            if input("\nSend this reminder? (y/n): ").strip().lower() == "y":
                ai_writer.send_reminder_for(row, draft)
                print("Reminder sent.")

    elif choice == "4":
        print("\n" + ai_writer.monthly_summary())

    elif choice == "5":
        for r in db.list_invoices():
            print(r["invoice_number"], r["client_name"], r["status"], f"${r['usd_amount']}",
                  "due", r["due_date"], "reminders:", r["reminders_sent"])

    elif choice == "6":
        for r in db.list_invoices():
            print(f"Invoice {r['invoice_number']} ({r['status']}): {r['pay_url']}")

    elif choice == "q":
        break