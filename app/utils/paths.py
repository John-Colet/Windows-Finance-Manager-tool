"""Figures out where this app stores its files on the user's computer.

Everything lives under %LOCALAPPDATA%\\FinanceManager by default:
  - FinanceManager.db        -> the database file (all your data)
  - db_location.txt          -> a small text file that remembers WHERE the
                                 database file actually is, so a later phase
                                 can let you move/choose the database location
                                 without changing any code.
  - Backups\\                 -> where backup copies are saved by default.
"""

import os
from pathlib import Path

APP_FOLDER_NAME = "FinanceManager"


def get_app_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    app_dir = Path(base) / APP_FOLDER_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_database_path() -> Path:
    location_file = get_app_data_dir() / "db_location.txt"
    default_db_path = get_app_data_dir() / "FinanceManager.db"

    if location_file.exists():
        stored_path = Path(location_file.read_text(encoding="utf-8").strip())
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        return stored_path

    location_file.write_text(str(default_db_path), encoding="utf-8")
    return default_db_path


def get_backups_dir() -> Path:
    backups_dir = get_app_data_dir() / "Backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    return backups_dir
