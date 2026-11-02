"""The login screen: the first thing you see when the app starts."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QVBoxLayout, QWidget,
)

from app.models.user import LoginResult, any_users_exist, attempt_login
from app.ui.first_run_dialog import FirstRunDialog
from app.ui.main_window import MainWindow

APP_TITLE = "Finance Manager"
CREDIT_LINE = "© 2026 Ireneo John II Colet — john.colet.ca"


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.setMinimumWidth(380)
        self.main_window: Optional[MainWindow] = None

        self._build_ui()
        self._maybe_show_first_run()

    def _build_ui(self) -> None:
        title = QLabel(APP_TITLE)
        title.setObjectName("titleLabel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._on_login_clicked)

        form = QFormLayout()
        form.addRow("Username:", self.username_input)
        form.addRow("Password:", self.password_input)

        login_button = QPushButton("Log In")
        login_button.setObjectName("primaryButton")
        login_button.clicked.connect(self._on_login_clicked)

        self.status_label = QLabel("")
        self.status_label.setObjectName("errorLabel")
        self.status_label.setWordWrap(True)

        credit_label = QLabel(CREDIT_LINE)
        credit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        credit_label.setObjectName("creditLabel")

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(login_button)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addLayout(button_row)
        layout.addStretch()
        layout.addWidget(credit_label)
        self.setLayout(layout)

    def _maybe_show_first_run(self) -> None:
        if not any_users_exist():
            FirstRunDialog(self).exec()

    def _on_login_clicked(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()

        if not username or not password:
            self.status_label.setText("Please enter both username and password.")
            return

        result, user, remaining = attempt_login(username, password)

        if result == LoginResult.SUCCESS:
            self.status_label.setText("")
            self.password_input.clear()
            self.main_window = MainWindow(user)
            self.main_window.logged_out.connect(self._on_logged_out)
            self.main_window.show()
            self.hide()
        elif result == LoginResult.ACCOUNT_LOCKED:
            minutes_left = max(1, int(remaining.total_seconds() // 60) + 1) if remaining else "a few"
            self.status_label.setText(
                f"Too many failed attempts. This account is locked for about {minutes_left} more minute(s)."
            )
        elif result == LoginResult.ACCOUNT_INACTIVE:
            self.status_label.setText("This account has been deactivated. Contact your administrator.")
        else:
            self.status_label.setText("Incorrect username or password.")
            self.password_input.clear()

    def _on_logged_out(self) -> None:
        self.username_input.clear()
        self.password_input.clear()
        self.status_label.setText("")
        self.show()
        if self.main_window is not None:
            self.main_window.deleteLater()
            self.main_window = None
