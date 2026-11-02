"""Income: salary, side income, and other sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.database.db import get_connection

SOURCE_TYPES = {"salary": "Salary", "side": "Side Income", "other": "Other"}
SOURCE_TYPE_VALUES = {label: value for value, label in SOURCE_TYPES.items()}

_SELECT_SQL = """
SELECT i.income_id, i.user_id, i.date, i.amount, i.source_name, i.source_type,
       i.is_taxable, i.tax_tag_id, t.name AS tax_tag_name, i.notes, i.created_at
FROM income i
LEFT JOIN tax_tags t ON t.tax_tag_id = i.tax_tag_id
"""


@dataclass
class Income:
    income_id: int
    user_id: int
    date: str
    amount: float
    source_name: str
    source_type: str
    is_taxable: bool
    tax_tag_id: Optional[int]
    tax_tag_name: Optional[str]
    notes: str
    created_at: str


def _row_to_income(row) -> Income:
    return Income(
        income_id=row["income_id"],
        user_id=row["user_id"],
        date=row["date"],
        amount=row["amount"],
        source_name=row["source_name"],
        source_type=row["source_type"],
        is_taxable=bool(row["is_taxable"]),
        tax_tag_id=row["tax_tag_id"],
        tax_tag_name=row["tax_tag_name"],
        notes=row["notes"] or "",
        created_at=row["created_at"],
    )


def list_income(start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[Income]:
    conn = get_connection()
    sql = _SELECT_SQL
    params: list = []
    if start_date and end_date:
        sql += " WHERE i.date BETWEEN ? AND ?"
        params.extend([start_date, end_date])
    sql += " ORDER BY i.date DESC, i.income_id DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_income(row) for row in rows]


def get_income(income_id: int) -> Optional[Income]:
    conn = get_connection()
    row = conn.execute(_SELECT_SQL + " WHERE i.income_id = ?", (income_id,)).fetchone()
    return _row_to_income(row) if row else None


def create_income(
    user_id: int, date: str, amount: float, source_name: str, source_type: str,
    is_taxable: bool, notes: str, tax_tag_id: Optional[int] = None,
) -> int:
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    cursor = conn.execute(
        """
        INSERT INTO income (user_id, date, amount, source_name, source_type, is_taxable, tax_tag_id, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, date, amount, source_name.strip(), source_type, 1 if is_taxable else 0,
         tax_tag_id, notes, now),
    )
    conn.commit()
    return cursor.lastrowid


def update_income(
    income_id: int, date: str, amount: float, source_name: str, source_type: str,
    is_taxable: bool, notes: str, tax_tag_id: Optional[int] = None,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE income SET date=?, amount=?, source_name=?, source_type=?, is_taxable=?, tax_tag_id=?, notes=?
        WHERE income_id=?
        """,
        (date, amount, source_name.strip(), source_type, 1 if is_taxable else 0, tax_tag_id, notes, income_id),
    )
    conn.commit()


def delete_income(income_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM income WHERE income_id = ?", (income_id,))
    conn.commit()
