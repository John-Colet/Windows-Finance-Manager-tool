"""Recurring monthly bills: track due dates, paid/unpaid status, and history."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from app.database.db import get_connection

FREQUENCIES = {
    "weekly": "Weekly", "biweekly": "Bi-weekly", "monthly": "Monthly", "yearly": "Yearly",
}
FREQUENCY_VALUES = {label: value for value, label in FREQUENCIES.items()}

REMINDER_WINDOW_DAYS = 7


@dataclass
class Bill:
    bill_id: int
    user_id: int
    name: str
    amount: float
    due_date: str
    frequency: str
    status: str
    notes: str
    created_at: str

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
        due_date=row["due_date"], frequency=row["frequency"], status=row["status"],
        notes=row["notes"] or "", created_at=row["created_at"],
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


def create_bill(user_id: int, name: str, amount: float, due_date: str, frequency: str, notes: str) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO bills (user_id, name, amount, due_date, frequency, status, notes, created_at)
        VALUES (?, ?, ?, ?, ?, 'unpaid', ?, ?)
        """,
        (user_id, name.strip(), amount, due_date, frequency, notes, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_bill(bill_id: int, name: str, amount: float, due_date: str, frequency: str, notes: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE bills SET name=?, amount=?, due_date=?, frequency=?, notes=? WHERE bill_id=?",
        (name.strip(), amount, due_date, frequency, notes, bill_id),
    )
    conn.commit()


def delete_bill(bill_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM bill_payments WHERE bill_id = ?", (bill_id,))
    conn.execute("DELETE FROM bills WHERE bill_id = ?", (bill_id,))
    conn.commit()


def list_bill_payments(bill_id: int):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM bill_payments WHERE bill_id = ? ORDER BY paid_date DESC", (bill_id,)
    ).fetchall()


def advance_due_date(iso_date: str, frequency: str) -> str:
    current = date.fromisoformat(iso_date)
    if frequency == "weekly":
        return (current + timedelta(weeks=1)).isoformat()
    if frequency == "biweekly":
        return (current + timedelta(weeks=2)).isoformat()
    if frequency == "monthly":
        month = current.month + 1
        year = current.year + (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(current.day, calendar.monthrange(year, month)[1])
        return date(year, month, day).isoformat()
    if frequency == "yearly":
        try:
            return current.replace(year=current.year + 1).isoformat()
        except ValueError:
            return current.replace(year=current.year + 1, day=28).isoformat()
    return iso_date


def mark_bill_paid(bill_id: int, paid_date: str, amount_paid: float) -> None:
    """Records the payment, then rolls the bill forward to its next due date."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO bill_payments (bill_id, paid_date, amount_paid) VALUES (?, ?, ?)",
        (bill_id, paid_date, amount_paid),
    )
    bill = get_bill(bill_id)
    next_due_date = advance_due_date(bill.due_date, bill.frequency)
    conn.execute(
        "UPDATE bills SET status = 'unpaid', due_date = ? WHERE bill_id = ?", (next_due_date, bill_id)
    )
    conn.commit()
