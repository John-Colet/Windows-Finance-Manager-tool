"""Daily expenses, with an optional receipt image stored inside the database.

An expense can optionally be linked to a debt in one of two directions:
  - charged_debt_id: this expense was CHARGED to a credit card -- it
    INCREASES that debt's balance (you now owe more).
  - linked_debt_id: this expense IS a payment toward a debt -- it
    DECREASES that debt's balance (you paid some of it off).
Only one of the two should be set at a time; the UI enforces this.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.database.db import get_connection
from app.models.debt import record_debt_payment, unlink_debt_payment

PAYMENT_METHODS = ["Cash", "Debit Card", "Credit Card", "E-Transfer", "Cheque", "Other"]

_SELECT_SQL = """
SELECT e.expense_id, e.user_id, e.name, e.date, e.amount, e.category_id, c.name AS category_name,
       e.payment_method, e.notes, e.receipt_filename,
       (e.receipt_image IS NOT NULL) AS has_receipt,
       e.tax_tag_id, t.name AS tax_tag_name,
       e.linked_debt_id, d1.creditor_name AS linked_debt_name,
       e.charged_debt_id, d2.creditor_name AS charged_debt_name,
       e.created_at, e.updated_at
FROM expenses e
JOIN categories c ON c.category_id = e.category_id
LEFT JOIN tax_tags t ON t.tax_tag_id = e.tax_tag_id
LEFT JOIN debts_i_owe d1 ON d1.debt_id = e.linked_debt_id
LEFT JOIN debts_i_owe d2 ON d2.debt_id = e.charged_debt_id
"""


@dataclass
class Expense:
    expense_id: int
    user_id: int
    name: str
    date: str
    amount: float
    category_id: int
    category_name: str
    payment_method: str
    notes: str
    has_receipt: bool
    receipt_filename: Optional[str]
    tax_tag_id: Optional[int]
    tax_tag_name: Optional[str]
    linked_debt_id: Optional[int]
    linked_debt_name: Optional[str]
    charged_debt_id: Optional[int]
    charged_debt_name: Optional[str]
    created_at: str
    updated_at: str


def _row_to_expense(row) -> Expense:
    return Expense(
        expense_id=row["expense_id"],
        user_id=row["user_id"],
        name=row["name"] or "",
        date=row["date"],
        amount=row["amount"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        payment_method=row["payment_method"] or "",
        notes=row["notes"] or "",
        has_receipt=bool(row["has_receipt"]),
        receipt_filename=row["receipt_filename"],
        tax_tag_id=row["tax_tag_id"],
        tax_tag_name=row["tax_tag_name"],
        linked_debt_id=row["linked_debt_id"],
        linked_debt_name=row["linked_debt_name"],
        charged_debt_id=row["charged_debt_id"],
        charged_debt_name=row["charged_debt_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_expenses(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[Expense]:
    conn = get_connection()
    sql = _SELECT_SQL
    params: list = []
    if start_date and end_date:
        sql += " WHERE e.date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    sql += " ORDER BY e.date DESC, e.expense_id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_expense(row) for row in rows]


def get_expense(expense_id: int) -> Optional[Expense]:
    conn = get_connection()
    row = conn.execute(_SELECT_SQL + " WHERE e.expense_id = ?", (expense_id,)).fetchone()
    return _row_to_expense(row) if row else None


def get_receipt_image(expense_id: int) -> Optional[bytes]:
    conn = get_connection()
    row = conn.execute("SELECT receipt_image FROM expenses WHERE expense_id = ?", (expense_id,)).fetchone()
    return row["receipt_image"] if row else None


def _apply_debt_links(
    expense_id: int, date: str, amount: float,
    linked_debt_id: Optional[int], charged_debt_id: Optional[int],
) -> None:
    """Applies the correct debt balance effect for this expense's current
    links. Call unlink_debt_payment first if this is an update (to reverse
    whatever the OLD links were) before calling this with the NEW links."""
    if charged_debt_id is not None:
        record_debt_payment(charged_debt_id, date, amount, source_type="expense", source_id=expense_id,
                             transaction_type="charge")
    elif linked_debt_id is not None:
        record_debt_payment(linked_debt_id, date, amount, source_type="expense", source_id=expense_id,
                             transaction_type="payment")


def create_expense(
    user_id: int, date: str, amount: float, category_id: int, payment_method: str, notes: str,
    name: str = "", tax_tag_id: Optional[int] = None,
    linked_debt_id: Optional[int] = None, charged_debt_id: Optional[int] = None,
    receipt_image: Optional[bytes] = None, receipt_filename: Optional[str] = None,
) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO expenses (
            user_id, name, date, amount, category_id, payment_method, notes,
            receipt_image, receipt_filename, tax_tag_id, linked_debt_id, charged_debt_id,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, name.strip(), date, amount, category_id, payment_method, notes,
         receipt_image, receipt_filename, tax_tag_id, linked_debt_id, charged_debt_id, now, now),
    )
    expense_id = cursor.lastrowid
    conn.commit()

    _apply_debt_links(expense_id, date, amount, linked_debt_id, charged_debt_id)

    return expense_id


def update_expense(
    expense_id: int, date: str, amount: float, category_id: int, payment_method: str, notes: str,
    name: str = "", tax_tag_id: Optional[int] = None,
    linked_debt_id: Optional[int] = None, charged_debt_id: Optional[int] = None,
    new_receipt_image: Optional[bytes] = None, new_receipt_filename: Optional[str] = None,
    remove_receipt: bool = False,
) -> None:
    conn = get_connection()
    now = datetime.utcnow().isoformat()

    # Reverse any previous debt link before applying the new values, so editing
    # the amount (or unlinking/relinking/switching direction) never leaves a
    # stale balance change.
    unlink_debt_payment("expense", expense_id)

    if new_receipt_image is not None:
        conn.execute(
            """
            UPDATE expenses SET name=?, date=?, amount=?, category_id=?, payment_method=?, notes=?,
                tax_tag_id=?, linked_debt_id=?, charged_debt_id=?, receipt_image=?, receipt_filename=?,
                updated_at=?
            WHERE expense_id=?
            """,
            (name.strip(), date, amount, category_id, payment_method, notes, tax_tag_id,
             linked_debt_id, charged_debt_id, new_receipt_image, new_receipt_filename, now, expense_id),
        )
    elif remove_receipt:
        conn.execute(
            """
            UPDATE expenses SET name=?, date=?, amount=?, category_id=?, payment_method=?, notes=?,
                tax_tag_id=?, linked_debt_id=?, charged_debt_id=?, receipt_image=NULL, receipt_filename=NULL,
                updated_at=?
            WHERE expense_id=?
            """,
            (name.strip(), date, amount, category_id, payment_method, notes, tax_tag_id,
             linked_debt_id, charged_debt_id, now, expense_id),
        )
    else:
        conn.execute(
            """
            UPDATE expenses SET name=?, date=?, amount=?, category_id=?, payment_method=?, notes=?,
                tax_tag_id=?, linked_debt_id=?, charged_debt_id=?, updated_at=?
            WHERE expense_id=?
            """,
            (name.strip(), date, amount, category_id, payment_method, notes, tax_tag_id,
             linked_debt_id, charged_debt_id, now, expense_id),
        )
    conn.commit()

    _apply_debt_links(expense_id, date, amount, linked_debt_id, charged_debt_id)


def delete_expense(expense_id: int) -> None:
    conn = get_connection()
    unlink_debt_payment("expense", expense_id)
    conn.execute("DELETE FROM expenses WHERE expense_id = ?", (expense_id,))
    conn.commit()
