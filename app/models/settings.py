"""App-wide settings, stored as simple key/value rows."""

from app.database.db import get_connection

DEFAULT_SETTINGS = {
    "currency": "CAD $",
    "date_format": "YYYY-MM-DD",
    "theme": "light",
    "session_timeout_minutes": "15",
    "backup_schedule": "daily",
    "backup_retention_count": "10",
}


def ensure_defaults() -> None:
    conn = get_connection()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_setting(key: str, default: str = "") -> str:
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()
