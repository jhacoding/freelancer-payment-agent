import os
import sqlite3
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "freelancer.db")


def _conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                invoice_id      TEXT PRIMARY KEY,
                invoice_number  TEXT,
                client_name     TEXT,
                client_email    TEXT,
                description     TEXT,
                amount          REAL,
                currency        TEXT,
                usd_amount      REAL,
                status          TEXT,
                due_date        TEXT,
                pay_url         TEXT,
                created_at      TEXT,
                paid_at         TEXT,
                reminders_sent  INTEGER DEFAULT 0
            )
        """)


def save_invoice(row: dict):
    row = {**row, "created_at": datetime.now().isoformat(timespec="seconds")}
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    with _conn() as c:
        c.execute(f"INSERT OR REPLACE INTO invoices ({cols}) VALUES ({marks})", list(row.values()))


def list_invoices():
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM invoices ORDER BY created_at DESC")]


def get_invoice_row(invoice_id: str):
    with _conn() as c:
        r = c.execute("SELECT * FROM invoices WHERE invoice_id = ?", (invoice_id,)).fetchone()
        return dict(r) if r else None


def update_status(invoice_id: str, status: str, paid_at: str | None = None):
    with _conn() as c:
        c.execute("UPDATE invoices SET status = ?, paid_at = COALESCE(?, paid_at) WHERE invoice_id = ?",
                  (status, paid_at, invoice_id))

def set_due_date(invoice_id: str, due_date: str):
    """Used by the demo 'simulate overdue' button."""
    with _conn() as c:
        c.execute("UPDATE invoices SET due_date = ? WHERE invoice_id = ?", (due_date, invoice_id))


def increment_reminders(invoice_id: str):
    with _conn() as c:
        c.execute("UPDATE invoices SET reminders_sent = reminders_sent + 1 WHERE invoice_id = ?", (invoice_id,))