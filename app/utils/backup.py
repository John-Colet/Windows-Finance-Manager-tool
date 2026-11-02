"""Backup, restore, and wipe the database file.

Backups use SQLite's own safe backup API (not a plain file copy), so a
backup is never taken mid-write. Automatic backups are checked once each
time the app starts (this app has no background service), and the oldest
copies beyond the configured retention count are deleted.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from app.database.db import close_connection, get_connection, initialize_database
from app.models.category import ensure_default_categories
from app.models.settings import ensure_defaults, get_setting, set_setting
from app.models.tax_tag import ensure_default_tax_tags
from app.utils.paths import get_backups_dir, get_database_path

BACKUP_FILENAME_PREFIX = "FinanceManager_backup_"


def _timestamped_filename() -> str:
    return f"{BACKUP_FILENAME_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"


def create_backup(destination_folder: str) -> Path:
    destination_folder_path = Path(destination_folder)
    destination_folder_path.mkdir(parents=True, exist_ok=True)
    destination_path = destination_folder_path / _timestamped_filename()

    source_conn = get_connection()
    dest_conn = sqlite3.connect(str(destination_path))
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
    return destination_path


def list_backups(folder: Optional[Path] = None) -> list[Path]:
    folder = folder or get_backups_dir()
    if not folder.exists():
        return []
    return sorted(folder.glob(f"{BACKUP_FILENAME_PREFIX}*.db"), key=lambda p: p.stat().st_mtime, reverse=True)


def prune_old_backups(folder: Optional[Path] = None, keep_count: int = 10) -> None:
    folder = folder or get_backups_dir()
    for old_backup in list_backups(folder)[keep_count:]:
        old_backup.unlink(missing_ok=True)


def is_scheduled_backup_due() -> bool:
    schedule = get_setting("backup_schedule", "daily")
    if schedule == "none":
        return False
    last_backup_at = get_setting("last_auto_backup_at", "")
    if not last_backup_at:
        return True
    last_date = datetime.fromisoformat(last_backup_at).date()
    today = date.today()
    if schedule == "daily":
        return today > last_date
    if schedule == "weekly":
        return (today - last_date).days >= 7
    if schedule == "monthly":
        return (today.year, today.month) != (last_date.year, last_date.month)
    return False


def run_scheduled_backup_if_due() -> Optional[Path]:
    if not is_scheduled_backup_due():
        return None
    keep_count = int(get_setting("backup_retention_count", "10"))
    backup_path = create_backup(str(get_backups_dir()))
    prune_old_backups(get_backups_dir(), keep_count)
    set_setting("last_auto_backup_at", datetime.now().isoformat())
    return backup_path


def _reseed_defaults_if_missing() -> None:
    ensure_defaults()
    ensure_default_categories()
    ensure_default_tax_tags()


def restore_backup(backup_file_path: str) -> None:
    """Replaces the live database with a backup file, then reopens it."""
    close_connection()
    db_path = get_database_path()
    shutil.copy2(backup_file_path, db_path)
    initialize_database()
    _reseed_defaults_if_missing()


def wipe_database() -> None:
    """Deletes ALL data and starts over with a fresh, empty database."""
    close_connection()
    db_path = get_database_path()
    if db_path.exists():
        db_path.unlink()
    initialize_database()
    _reseed_defaults_if_missing()
