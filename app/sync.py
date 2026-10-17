from datetime import datetime
from app import paypal, db

PAID_STATUSES = {"PAID", "MARKED_AS_PAID"}
CLOSED_STATUSES = PAID_STATUSES | {"CANCELLED", "REFUNDED", "MARKED_AS_REFUNDED"}


def sync_all() -> list[dict]:
    """Check PayPal for every open invoice. Returns the invoices that just became paid."""
    newly_paid = []
    for row in db.list_invoices():
        if row["status"] in CLOSED_STATUSES:
            continue
        info = paypal.get_invoice(row["invoice_id"])
        new_status = info["status"]
        if new_status == row["status"]:
            continue
        paid_at = datetime.now().isoformat(timespec="seconds") if new_status in PAID_STATUSES else None
        db.update_status(row["invoice_id"], new_status, paid_at)
        if new_status in PAID_STATUSES:
            newly_paid.append(db.get_invoice_row(row["invoice_id"]))
    return newly_paid