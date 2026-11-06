"""Schema migrations: additive-only changes applied to existing databases.

Every migration here only ADDS columns or backfills data -- it never
drops, renames, or rewrites anything that already exists, so upgrading
an existing database never loses data.
"""

import sqlite3

CURRENT_SCHEMA_VERSION = 4


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column_def: str) -> None:
    column_name = column_def.split()[0]
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column_name not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def _get_schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT version FROM schema_version").fetchone()
    return row["version"] if row else 0


def run_migrations(conn: sqlite3.Connection) -> None:
    version = _get_schema_version(conn)

    if version < 3:
        _migrate_to_v3(conn)
        version = 3

    if version < 4:
        _migrate_to_v4(conn)
        version = 4

    conn.execute("DELETE FROM schema_version")
    conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
    conn.commit()


def _migrate_to_v3(conn: sqlite3.Connection) -> None:
    # Expenses: a manual, free-text name, and an optional link to a debt payment.
    _add_column_if_missing(conn, "expenses", "name TEXT NOT NULL DEFAULT ''")
    _add_column_if_missing(conn, "expenses", "linked_debt_id INTEGER REFERENCES debts_i_owe(debt_id)")

    # Bills: a flexible custom recurring interval, replacing the fixed list.
    _add_column_if_missing(conn, "bills", "interval_unit TEXT")
    _add_column_if_missing(conn, "bills", "interval_count INTEGER")
    _add_column_if_missing(conn, "bill_payments", "linked_debt_id INTEGER REFERENCES debts_i_owe(debt_id)")

    # Debt payments: remember where a payment came from (a bill, an expense, or manual entry).
    _add_column_if_missing(conn, "debt_payments", "source_type TEXT")
    _add_column_if_missing(conn, "debt_payments", "source_id INTEGER")

    # Backfill interval_unit/interval_count for existing bills from their old frequency value.
    conn.execute(
        "UPDATE bills SET interval_unit='weeks', interval_count=1 "
        "WHERE frequency='weekly' AND interval_unit IS NULL"
    )
    conn.execute(
        "UPDATE bills SET interval_unit='weeks', interval_count=2 "
        "WHERE frequency='biweekly' AND interval_unit IS NULL"
    )
    conn.execute(
        "UPDATE bills SET interval_unit='months', interval_count=1 "
        "WHERE frequency='monthly' AND interval_unit IS NULL"
    )
    conn.execute(
        "UPDATE bills SET interval_unit='months', interval_count=12 "
        "WHERE frequency='yearly' AND interval_unit IS NULL"
    )
    # Safety net: anything still unset (shouldn't happen) defaults to monthly.
    conn.execute(
        "UPDATE bills SET interval_unit='months', interval_count=1 WHERE interval_unit IS NULL"
    )

    conn.commit()


def _migrate_to_v4(conn: sqlite3.Connection) -> None:
    # Expenses can now also be CHARGED to a credit card (increases its balance),
    # separate from linked_debt_id which PAYS DOWN a debt (decreases its balance).
    _add_column_if_missing(conn, "expenses", "charged_debt_id INTEGER REFERENCES debts_i_owe(debt_id)")

    # Every debt_payments row now records whether it was a payment (decreases
    # balance) or a charge (increases balance). All existing rows were payments.
    _add_column_if_missing(conn, "debt_payments", "transaction_type TEXT DEFAULT 'payment'")
    conn.execute("UPDATE debt_payments SET transaction_type = 'payment' WHERE transaction_type IS NULL")

    conn.commit()
