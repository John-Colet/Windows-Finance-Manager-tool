"""The main window after login: sidebar + pages, auto-logout, About dialog."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from app.models.settings import get_setting
from app.models.user import User, log_logout
from app.ui.backup_page import BackupPage
from app.ui.bills_page import BillsPage
from app.ui.dashboard_page import DashboardPage
from app.ui.debts_page import DebtsPage
from app.ui.expenses_page import ExpensesPage
from app.ui.income_page import IncomePage
from app.ui.reports_page import ReportsPage
from app.ui.settings_page import SettingsPage
from app.ui.taxes_page import TaxesPage
from app.ui.users_page import UsersPage

APP_TITLE = "Finance Manager"
CREDIT_LINE = "© 2026 Ireneo John II Colet — john.colet.ca"

DASHBOARD_PAGE_INDEX = 0


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Finance Manager")
        self.setMinimumWidth(360)

        title = QLabel(APP_TITLE)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version = QLabel("Version 0.9 (Phase 9 - Backup & Restore)")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit = QLabel(CREDIT_LINE)
        credit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(version)
        layout.addWidget(credit)
        layout.addWidget(close_button)
        self.setLayout(layout)


class MainWindow(QMainWindow):
    logged_out = Signal()

    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self.setWindowTitle(f"{APP_TITLE} - {user.full_name} ({user.role.capitalize()})")
        self.resize(1000, 650)

        self._build_ui()
        self._setup_inactivity_timer()

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 20, 0, 20)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        QListWidgetItem("Dashboard", self.nav_list)
        QListWidgetItem("Expenses", self.nav_list)
        QListWidgetItem("Income", self.nav_list)
        QListWidgetItem("Bills", self.nav_list)
        QListWidgetItem("Debts", self.nav_list)
        QListWidgetItem("Taxes", self.nav_list)
        QListWidgetItem("Reports", self.nav_list)
        QListWidgetItem("Settings", self.nav_list)
        if self.user.is_admin:
            QListWidgetItem("Users", self.nav_list)
            QListWidgetItem("Backup & Restore", self.nav_list)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        about_button = QPushButton("About")
        about_button.setObjectName("sidebarButton")
        about_button.clicked.connect(self._show_about)

        logout_button = QPushButton("Log Out")
        logout_button.setObjectName("logoutButton")
        logout_button.clicked.connect(self._on_logout_clicked)

        sidebar_layout.addWidget(self.nav_list)
        sidebar_layout.addStretch()
        sidebar_layout.addWidget(about_button)
        sidebar_layout.addWidget(logout_button)
        sidebar.setLayout(sidebar_layout)

        self.pages = QStackedWidget()
        self.dashboard_page = DashboardPage(self.user)
        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(ExpensesPage(self.user))
        self.pages.addWidget(IncomePage(self.user))
        self.pages.addWidget(BillsPage(self.user))
        self.pages.addWidget(DebtsPage(self.user))
        self.pages.addWidget(TaxesPage())
        self.pages.addWidget(ReportsPage())
        self.pages.addWidget(SettingsPage())
        if self.user.is_admin:
            self.pages.addWidget(UsersPage(self.user))
            backup_page = BackupPage()
            backup_page.force_logout_requested.connect(self._logout)
            self.pages.addWidget(backup_page)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.pages, stretch=1)
        central.setLayout(root_layout)
        self.setCentralWidget(central)

    def _on_nav_changed(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        if index == DASHBOARD_PAGE_INDEX:
            self.dashboard_page.refresh()

    def _show_about(self) -> None:
        AboutDialog(self).exec()

    def _setup_inactivity_timer(self) -> None:
        timeout_minutes = int(get_setting("session_timeout_minutes", "15"))
        self.timeout_ms = timeout_minutes * 60 * 1000
        self.inactivity_timer = QTimer(self)
        self.inactivity_timer.setSingleShot(True)
        self.inactivity_timer.timeout.connect(self._on_inactivity_timeout)
        self.inactivity_timer.start(self.timeout_ms)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (
            QEvent.Type.MouseMove,
            QEvent.Type.MouseButtonPress,
            QEvent.Type.KeyPress,
            QEvent.Type.Wheel,
        ):
            self.inactivity_timer.start(self.timeout_ms)
        return super().eventFilter(watched, event)

    def _on_inactivity_timeout(self) -> None:
        QMessageBox.information(self, "Logged Out", "You were logged out automatically due to inactivity.")
        self._logout()

    def _on_logout_clicked(self) -> None:
        self._logout()

    def _logout(self) -> None:
        QApplication.instance().removeEventFilter(self)
        log_logout(self.user)
        self.close()
        self.logged_out.emit()
