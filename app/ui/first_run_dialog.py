"""Shown once, the very first time the app runs: create the Administrator."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.models.user import create_user
from app.utils.security import MIN_PASSWORD_LENGTH


class FirstRunDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Administrator Account")
        self.setMinimumWidth(420)
        self.setModal(True)

        intro = QLabel(
            "Welcome! This looks like the first time the app is running.\n"
            "Create the Administrator account that will manage this app."
        )
        intro.setWordWrap(True)

        self.username_input = QLineEdit()
        self.full_name_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("Username:", self.username_input)
        form.addRow("Full name:", self.full_name_input)
        form.addRow("Password:", self.password_input)
        form.addRow("Confirm password:", self.confirm_input)

        create_button = QPushButton("Create Administrator Account")
        create_button.setObjectName("primaryButton")
        create_button.clicked.connect(self._on_create_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addWidget(create_button)

        layout = QVBoxLayout()
        layout.addWidget(intro)
        layout.addLayout(form)
        layout.addLayout(buttons_row)
        self.setLayout(layout)

    def _on_create_clicked(self) -> None:
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        password = self.password_input.text()
        confirm = self.confirm_input.text()

        if not username or not full_name:
            QMessageBox.warning(self, "Missing information", "Please fill in all fields.")
            return

        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(
                self, "Password too short",
                f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
            )
            return

        if password != confirm:
            QMessageBox.warning(self, "Passwords don't match", "The two passwords you entered do not match.")
            return

        create_user(username=username, full_name=full_name, plain_password=password, role="admin")
        QMessageBox.information(self, "Account created", "Administrator account created. You can now log in.")
        self.accept()
