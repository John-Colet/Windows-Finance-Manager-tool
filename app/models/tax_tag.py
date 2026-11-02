"""Tax tags: an editable list used to flag expenses/income as tax-related.

The app only tags and totals these for you -- it does not decide what is
actually deductible. Always confirm with your accountant or the CRA.
"""

from __future__ import annotations

from typing import Optional

from app.database.db import get_connection

DEFAULT_TAX_TAGS = [
    ("Medical", "Medical and dental expenses"),
    ("Charitable Donation", "Donations to registered charities"),
    ("Childcare", "Child care expenses"),
    ("Employment Expense", "Employment-related expenses"),
    ("Tuition", "Tuition and education expenses"),
    ("Home Office", "Home office / work-from-home expenses"),
    ("Business Expense", "Self-employment / business expenses"),
    ("Other Deductible", "Other potentially deductible expense"),
]


def ensure_default_tax_tags() -> None:
    conn = get_connection()
    for name, description in DEFAULT_TAX_TAGS:
        conn.execute(
            "INSERT OR IGNORE INTO tax_tags (name, description) VALUES (?, ?)",
            (name, description),
        )
    conn.commit()


def list_tax_tags():
    conn = get_connection()
    return conn.execute("SELECT * FROM tax_tags ORDER BY name COLLATE NOCASE").fetchall()


def tax_tag_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT tax_tag_id FROM tax_tags WHERE name = ? COLLATE NOCASE AND tax_tag_id != ?",
        (name.strip(), exclude_id or -1),
    ).fetchone()
    return row is not None


def create_tax_tag(name: str, description: str = "") -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO tax_tags (name, description) VALUES (?, ?)", (name.strip(), description.strip())
    )
    conn.commit()
    return cursor.lastrowid


def update_tax_tag(tax_tag_id: int, name: str, description: str = "") -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE tax_tags SET name = ?, description = ? WHERE tax_tag_id = ?",
        (name.strip(), description.strip(), tax_tag_id),
    )
    conn.commit()


def tax_tag_in_use(tax_tag_id: int) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM expenses WHERE tax_tag_id = ? "
        "UNION SELECT 1 FROM income WHERE tax_tag_id = ? LIMIT 1",
        (tax_tag_id, tax_tag_id),
    ).fetchone()
    return row is not None


def delete_tax_tag(tax_tag_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM tax_tags WHERE tax_tag_id = ?", (tax_tag_id,))
    conn.commit()
