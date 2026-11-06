"""Database connection and schema setup.

All tables for every phase are created here with CREATE TABLE IF NOT
EXISTS, so running this against an existing database never destroys your
data -- it only adds whatever is missing.
"""

import sqlite3
from contextlib import contextmanager

from app.database.migrations import CURRENT_SCHEMA_VERSION, run_migrations
from app.utils.paths import get_database_path

SCHEMA_VERSION = CURRENT_SCHEMA_VERSION

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    is_active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    category_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER
);

CREATE TABLE IF NOT EXISTS tax_tags (
    tax_tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE IF NOT EXISTS expenses (
    expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL DEFAULT '',
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    payment_method TEXT,
    notes TEXT,
    receipt_image BLOB,
    receipt_filename TEXT,
    tax_tag_id INTEGER REFERENCES tax_tags(tax_tag_id),
    linked_debt_id INTEGER REFERENCES debts_i_owe(debt_id),
    charged_debt_id INTEGER REFERENCES debts_i_owe(debt_id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS income (
    income_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('salary', 'side', 'other')),
    is_taxable INTEGER NOT NULL DEFAULT 1,
    tax_tag_id INTEGER REFERENCES tax_tags(tax_tag_id),
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
    bill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    name TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'biweekly', 'monthly', 'yearly')),
    interval_unit TEXT NOT NULL CHECK (interval_unit IN ('days', 'weeks', 'months')) DEFAULT 'months',
    interval_count INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL CHECK (status IN ('paid', 'unpaid')) DEFAULT 'unpaid',
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bill_payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bill_id INTEGER NOT NULL REFERENCES bills(bill_id),
    paid_date TEXT NOT NULL,
    amount_paid REAL NOT NULL,
    linked_debt_id INTEGER REFERENCES debts_i_owe(debt_id)
);

CREATE TABLE IF NOT EXISTS debts_i_owe (
    debt_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    creditor_name TEXT NOT NULL,
    debt_type TEXT NOT NULL CHECK (debt_type IN ('credit_card', 'loan', 'other')),
    balance REAL NOT NULL,
    interest_rate REAL,
    minimum_payment REAL,
    due_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS debt_payments (
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    debt_id INTEGER NOT NULL REFERENCES debts_i_owe(debt_id),
    payment_date TEXT NOT NULL,
    amount REAL NOT NULL,
    source_type TEXT CHECK (source_type IN ('manual', 'bill', 'expense')),
    source_id INTEGER,
    transaction_type TEXT NOT NULL CHECK (transaction_type IN ('payment', 'charge')) DEFAULT 'payment'
);

CREATE TABLE IF NOT EXISTS debts_owed_to_me (
    loan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    debtor_name TEXT NOT NULL,
    amount REAL NOT NULL,
    date_lent TEXT NOT NULL,
    due_date TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS loan_repayments (
    repayment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL REFERENCES debts_owed_to_me(loan_id),
    repayment_date TEXT NOT NULL,
    amount REAL NOT NULL
);
"""

_connection: sqlite3.Connection | None = None


def get_connection() -> sqlite3.Connection:
    global _connection
    if _connection is None:
        db_path = get_database_path()
        _connection = sqlite3.connect(str(db_path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
    return _connection


def close_connection() -> None:
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def initialize_database() -> None:
    conn = get_connection()
    conn.executescript(_SCHEMA_SQL)

    row = conn.execute("SELECT version FROM schema_version").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()

    run_migrations(conn)


@contextmanager
def transaction():
    """Use with 'with transaction() as conn:' to group several writes safely."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
