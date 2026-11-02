"""Entry point. Run this with:  py -m app.main   (from the finance-manager folder)"""

import sys

from PySide6.QtWidgets import QApplication

from app.database.db import initialize_database
from app.models.category import ensure_default_categories
from app.models.settings import ensure_defaults, get_setting
from app.models.tax_tag import ensure_default_tax_tags
from app.ui.login_window import LoginWindow
from app.ui.styles import get_stylesheet
from app.utils.backup import run_scheduled_backup_if_due


def main() -> None:
    initialize_database()
    ensure_defaults()
    ensure_default_categories()
    ensure_default_tax_tags()
    run_scheduled_backup_if_due()

    app = QApplication(sys.argv)
    app.setStyleSheet(get_stylesheet(get_setting("theme", "light")))

    window = LoginWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
