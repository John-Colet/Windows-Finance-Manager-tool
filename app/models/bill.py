"""Recurring bills: flexible custom intervals, paid/unpaid status, and history."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from app.database.db import get_connection
from app.models.debt import record_debt_payment, unlink_debt_payment

REMINDER_WINDOW_DAYS = 7

# Quick-pick presets shown in the UI: (label, interval_unit, interval_count).
# Users can also choose "Custom..." in the UI to type any unit/count.
INTERVAL_PRESETS = [
    ("Weekly", "weeks", 1),
    ("Every 2 Weeks", "weeks", 2),
    ("Monthly", "months", 1),
    ("Every 2 Months", "months", 2),
    ("Every 3 Months", "months", 3),
    ("Yearly", "months", 12),
]

_UNIT_LABELS = {"days": "Day", "weeks": "Week", "months": "Month"}


def format_frequency(interval_unit: str, interval_count: int) -> str:
    for label, unit, count in INTERVAL_PRESETS:
        if unit == interval_unit and count == interval_count:
            return label
    unit_label = _UNIT_LABELS.get(interval_unit, interval_unit)
    plural = "s" if interval_count != 1 else ""
    return f"Every {interval_count} {unit_label}{plural}"


def _legacy_frequency_for(interval_unit: str, interval_count: int) -> str:
    """Best-fit value for the old 'frequency' column, kept only so older
    database files (whose frequency column still requires one of these
    exact values) keep working. The app no longer reads this column."""
    if interval_unit == "weeks" and interval_count == 1:
        return "weekly"
    if interval_unit == "weeks" and interval_count == 2:
        return "biweekly"
    if interval_unit == "months" and interval_count == 12:
        return "yearly"
    return "monthly"


@dataclass
class Bill:
    bill_id: int
    user_id: int
    name: str
    amount: float
    due_date: str
    interval_unit: str
    interval_count: int
    status: str
    notes: str
    created_at: str

    @property
    def frequency_label(self) -> str:
        return format_frequency(self.interval_unit, self.interval_count)

    @property
    def is_overdue(self) -> bool:
        return self.status == "unpaid" and date.fromisoformat(self.due_date) < date.today()

    @property
    def is_due_soon(self) -> bool:
        if self.status != "unpaid" or self.is_overdue:
            return False
        days_until = (date.fromisoformat(self.due_date) - date.today()).days
        return 0 <= days_until <= REMINDER_WINDOW_DAYS


def _row_to_bill(row) -> Bill:
    return Bill(
        bill_id=row["bill_id"], user_id=row["user_id"], name=row["name"], amount=row["amount"],
        due_date=row["due_date"], interval_unit=row["interval_unit"], interval_count=row["interval_count"],
        status=row["status"], notes=row["notes"] or "", created_at=row["created_at"],
    )


def list_bills() -> list[Bill]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM bills ORDER BY due_date ASC").fetchall()
    return [_row_to_bill(row) for row in rows]


def get_bill(bill_id: int) -> Optional[Bill]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM bills WHERE bill_id = ?", (bill_id,)).fetchone()
    return _row_to_bill(row) if row else None


def get_due_soon_or_overdue_bills() -> list[Bill]:
    return [bill for bill in list_bills() if bill.is_overdue or bill.is_due_soon]


def get_upcoming_bills(limit: int = 5) -> list[Bill]:
    """The next unpaid bills coming due, soonest first (includes overdue ones)."""
    unpaid = [bill for bill in list_bills() if bill.status == "unpaid"]
    return sorted(unpaid, key=lambda bill: bill.due_date)[:limit]


def create_bill(
    user_id: int, name: str, amount: float, due_date: str,
    interval_unit: str, interval_count: int, notes: str,
) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    legacy_frequency = _legacy_frequency_for(interval_unit, interval_count)
    cursor = conn.execute(
        """
        INSERT INTO bills (user_id, name, amount, due_date, frequency, interval_unit, interval_count,
            status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'unpaid', ?, ?)
        """,
        (user_id, name.strip(), amount, due_date, legacy_frequency, interval_unit, interval_count, notes, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_bill(
    bill_id: int, name: str, amount: float, due_date: str,
    interval_unit: str, interval_count: int, notes: str,
) -> None:
    conn = get_connection()
    legacy_frequency = _legacy_frequency_for(interval_unit, interval_count)
    conn.execute(
        "UPDATE bills SET name=?, amount=?, due_date=?, frequency=?, interval_unit=?, interval_count=?, "
        "notes=? WHERE bill_id=?",
        (name.strip(), amount, due_date, legacy_frequency, interval_unit, interval_count, notes, bill_id),
    )
    conn.commit()


def delete_bill(bill_id: int) -> None:
    conn = get_connection()
    for payment in list_bill_payments(bill_id):
        unlink_debt_payment("bill", payment["payment_id"])
    conn.execute("DELETE FROM bill_payments WHERE bill_id = ?", (bill_id,))
    conn.execute("DELETE FROM bills WHERE bill_id = ?", (bill_id,))
    conn.commit()


def list_bill_payments(bill_id: int):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM bill_payments WHERE bill_id = ? ORDER BY paid_date DESC", (bill_id,)
    ).fetchall()


def list_all_bill_payments():
    """Every payment, for every bill, in one combined history view."""
    conn = get_connection()
    return conn.execute(
        """
        SELECT bp.payment_id, bp.bill_id, b.name AS bill_name, bp.paid_date, bp.amount_paid,
               bp.linked_debt_id, d.creditor_name AS linked_debt_name
        FROM bill_payments bp
        JOIN bills b ON b.bill_id = bp.bill_id
        LEFT JOIN debts_i_owe d ON d.debt_id = bp.linked_debt_id
        ORDER BY bp.paid_date DESC, bp.payment_id DESC
        """
    ).fetchall()


def advance_due_date(iso_date: str, interval_unit: str, interval_count: int) -> str:
    current = date.fromisoformat(iso_date)
    if interval_unit == "days":
        return (current + timedelta(days=interval_count)).isoformat()
    if interval_unit == "weeks":
        return (current + timedelta(weeks=interval_count)).isoformat()
    if interval_unit == "months":
        total_months = current.month - 1 + interval_count
        year = current.year + total_months // 12
        month = total_months % 12 + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    return iso_date


def mark_bill_paid(bill_id: int, paid_date: str, amount_paid: float, linked_debt_id: Optional[int] = None) -> None:
    """Records the payment, rolls the bill to its next due date, and -- if a
    debt was chosen -- reduces that debt's balance by the same amount."""
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO bill_payments (bill_id, paid_date, amount_paid, linked_debt_id) VALUES (?, ?, ?, ?)",
        (bill_id, paid_date, amount_paid, linked_debt_id),
    )
    payment_id = cursor.lastrowid
    conn.commit()

    if linked_debt_id is not None:
        record_debt_payment(linked_debt_id, paid_date, amount_paid, source_type="bill", source_id=payment_id)

    bill = get_bill(bill_id)
    next_due_date = advance_due_date(bill.due_date, bill.interval_unit, bill.interval_count)
    conn.execute(
        "UPDATE bills SET status = 'unpaid', due_date = ? WHERE bill_id = ?", (next_due_date, bill_id)
    )
    conn.commit()
