"""Expense categories: a simple editable list."""

from __future__ import annotations

from typing import Optional

from app.database.db import get_connection

DEFAULT_CATEGORIES = [
    "Groceries", "Gas/Transportation", "Utilities", "Rent/Mortgage",
    "Insurance", "Dining Out", "Entertainment", "Healthcare",
    "Clothing", "Subscriptions", "Education", "Other",
]


def ensure_default_categories() -> None:
    conn = get_connection()
    for name in DEFAULT_CATEGORIES:
        conn.execute(
            "INSERT OR IGNORE INTO categories (name, is_default, created_by) VALUES (?, 1, NULL)",
            (name,),
        )
    conn.commit()


def list_categories():
    conn = get_connection()
    return conn.execute("SELECT * FROM categories ORDER BY name COLLATE NOCASE").fetchall()


def category_name_exists(name: str, exclude_id: Optional[int] = None) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT category_id FROM categories WHERE name = ? COLLATE NOCASE AND category_id != ?",
        (name.strip(), exclude_id or -1),
    ).fetchone()
    return row is not None


def create_category(name: str) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO categories (name, is_default, created_by) VALUES (?, 0, NULL)",
        (name.strip(),),
    )
    conn.commit()
    return cursor.lastrowid


def rename_category(category_id: int, new_name: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE categories SET name = ? WHERE category_id = ?", (new_name.strip(), category_id))
    conn.commit()


def category_in_use(category_id: int) -> bool:
    conn = get_connection()
    row = conn.execute("SELECT 1 FROM expenses WHERE category_id = ? LIMIT 1", (category_id,)).fetchone()
    return row is not None


def delete_category(category_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM categories WHERE category_id = ?", (category_id,))
    conn.commit()
