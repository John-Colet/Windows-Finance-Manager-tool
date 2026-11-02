"""Aggregation queries behind the Tax Summary, Reports, and Dashboard pages."""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from app.database.db import get_connection


def get_available_years() -> list[int]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT substr(date, 1, 4) AS year FROM expenses "
        "UNION SELECT DISTINCT substr(date, 1, 4) AS year FROM income "
        "ORDER BY year"
    ).fetchall()
    years = sorted({int(row["year"]) for row in rows if row["year"]})
    return years


def get_yearly_tax_summary(year: int) -> dict:
    conn = get_connection()
    start, end = f"{year}-01-01", f"{year}-12-31"

    expenses_by_tag = conn.execute(
        """
        SELECT t.name AS tax_tag_name, SUM(e.amount) AS total, COUNT(*) AS count
        FROM expenses e JOIN tax_tags t ON t.tax_tag_id = e.tax_tag_id
        WHERE e.date BETWEEN ? AND ?
        GROUP BY e.tax_tag_id
        ORDER BY t.name COLLATE NOCASE
        """,
        (start, end),
    ).fetchall()

    income_by_tag = conn.execute(
        """
        SELECT t.name AS tax_tag_name, SUM(i.amount) AS total, COUNT(*) AS count
        FROM income i JOIN tax_tags t ON t.tax_tag_id = i.tax_tag_id
        WHERE i.date BETWEEN ? AND ?
        GROUP BY i.tax_tag_id
        ORDER BY t.name COLLATE NOCASE
        """,
        (start, end),
    ).fetchall()

    taxable_income_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE date BETWEEN ? AND ? AND is_taxable = 1",
        (start, end),
    ).fetchone()["total"]

    non_taxable_income_total = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE date BETWEEN ? AND ? AND is_taxable = 0",
        (start, end),
    ).fetchone()["total"]

    total_tagged_expenses = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date BETWEEN ? AND ? AND tax_tag_id IS NOT NULL",
        (start, end),
    ).fetchone()["total"]

    return {
        "year": year,
        "expenses_by_tag": [dict(row) for row in expenses_by_tag],
        "income_by_tag": [dict(row) for row in income_by_tag],
        "taxable_income_total": taxable_income_total,
        "non_taxable_income_total": non_taxable_income_total,
        "total_tagged_expenses": total_tagged_expenses,
    }


def get_period_range(preset: str) -> tuple[str, str]:
    """Returns (start_date, end_date) ISO strings for a named preset period."""
    today = date.today()
    if preset == "This Week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat()
    if preset == "This Month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if preset == "Last 6 Months":
        month = today.month - 6
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        last_day = calendar.monthrange(year, month)[1]
        start = date(year, month, min(today.day, last_day))
        return start.isoformat(), today.isoformat()
    if preset == "This Year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    return today.replace(day=1).isoformat(), today.isoformat()


def get_summary(start_date: str, end_date: str) -> dict:
    conn = get_connection()

    total_expenses = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date BETWEEN ? AND ?",
        (start_date, end_date),
    ).fetchone()["total"]

    total_income = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE date BETWEEN ? AND ?",
        (start_date, end_date),
    ).fetchone()["total"]

    expenses_by_category = conn.execute(
        """
        SELECT c.name AS category_name, SUM(e.amount) AS total
        FROM expenses e JOIN categories c ON c.category_id = e.category_id
        WHERE e.date BETWEEN ? AND ?
        GROUP BY e.category_id
        ORDER BY total DESC
        """,
        (start_date, end_date),
    ).fetchall()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_savings": total_income - total_expenses,
        "expenses_by_category": [dict(row) for row in expenses_by_category],
    }


def get_monthly_trend(months_back: int = 6) -> list[dict]:
    """Income/expense totals for each of the last N months, oldest first."""
    conn = get_connection()
    today = date.today()

    months = []
    for i in range(months_back - 1, -1, -1):
        month = today.month - i
        year = today.year
        while month <= 0:
            month += 12
            year -= 1
        months.append((year, month))

    results = []
    for year, month in months:
        start = f"{year:04d}-{month:02d}-01"
        last_day = calendar.monthrange(year, month)[1]
        end = f"{year:04d}-{month:02d}-{last_day:02d}"
        income_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM income WHERE date BETWEEN ? AND ?", (start, end)
        ).fetchone()["total"]
        expense_total = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE date BETWEEN ? AND ?", (start, end)
        ).fetchone()["total"]
        results.append({"label": f"{year:04d}-{month:02d}", "income": income_total, "expense": expense_total})
    return results
