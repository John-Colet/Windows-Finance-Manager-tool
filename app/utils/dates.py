"""Date formatting that respects the user's chosen date format setting.

Dates are always STORED in the database as ISO text (YYYY-MM-DD), which
sorts correctly and is unambiguous. Only the on-screen DISPLAY format
changes based on Settings.
"""

from __future__ import annotations

from datetime import date, datetime

from app.models.settings import get_setting

_PYTHON_FORMAT_MAP = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
}

_QT_FORMAT_MAP = {
    "YYYY-MM-DD": "yyyy-MM-dd",
    "DD/MM/YYYY": "dd/MM/yyyy",
    "MM/DD/YYYY": "MM/dd/yyyy",
}


def get_display_format() -> str:
    return _PYTHON_FORMAT_MAP.get(get_setting("date_format", "YYYY-MM-DD"), "%Y-%m-%d")


def get_qt_display_format() -> str:
    return _QT_FORMAT_MAP.get(get_setting("date_format", "YYYY-MM-DD"), "yyyy-MM-dd")


def iso_to_display(iso_date_str: str) -> str:
    if not iso_date_str:
        return ""
    try:
        parsed = datetime.strptime(iso_date_str, "%Y-%m-%d").date()
    except ValueError:
        return iso_date_str
    return parsed.strftime(get_display_format())


def today_iso() -> str:
    return date.today().isoformat()
