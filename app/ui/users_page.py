"""Administrator-only screen: add, edit, deactivate, delete users, reset passwords."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.models.user import (
    User, count_active_admins, create_user, delete_user, list_users,
    reset_password, set_user_active, update_user, username_exists,
)
from app.utils.security import MIN_PASSWORD_LENGTH

ROLE_LABELS = {"admin": "Administrator", "user": "Regular User"}
ROLE_VALUES = {label: value for value, label in ROLE_LABELS.items()}


class _UserFormDialog(QDialog):
    """Shared form for both 'Add User' and 'Edit User'."""

    def __init__(self, parent=None, existing_user: Optional[User] = None):
        super().__init__(parent)
        self.existing_user = existing_user
        self.setWindowTitle("Edit User" if existing_user else "Add User")
        self.setMinimumWidth(380)

        self.username_input = QLineEdit()
        self.full_name_input = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItems(ROLE_LABELS.values())

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("Username:", self.username_input)
        form.addRow("Full name:", self.full_name_input)
        form.addRow("Role:", self.role_combo)

        if existing_user is None:
            form.addRow("Password:", self.password_input)
            form.addRow("Confirm password:", self.confirm_input)
            self.username_input.setText("")
        else:
            self.username_input.setText(existing_user.username)
            self.full_name_input.setText(existing_user.full_name)
            self.role_combo.setCurrentText(ROLE_LABELS[existing_user.role])

        save_button = QPushButton("Save")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._on_save_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addWidget(save_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons_row)
        self.setLayout(layout)

    def _on_save_clicked(self) -> None:
        username = self.username_input.text().strip()
        full_name = self.full_name_input.text().strip()
        role = ROLE_VALUES[self.role_combo.currentText()]

        if not username or not full_name:
            QMessageBox.warning(self, "Missing information", "Please fill in all fields.")
            return

        exclude_id = self.existing_user.user_id if self.existing_user else None
        if username_exists(username, exclude_user_id=exclude_id):
            QMessageBox.warning(self, "Username taken", "That username is already in use.")
            return

        if self.existing_user and self.existing_user.role == "admin" and role != "admin":
            if count_active_admins(exclude_user_id=self.existing_user.user_id) == 0:
                QMessageBox.warning(
                    self, "Can't remove last Administrator",
                    "At least one active Administrator account must remain.",
                )
                return

        if self.existing_user is None:
            password = self.password_input.text()
            confirm = self.confirm_input.text()
            if len(password) < MIN_PASSWORD_LENGTH:
                QMessageBox.warning(
                    self, "Password too short",
                    f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
                )
                return
            if password != confirm:
                QMessageBox.warning(self, "Passwords don't match", "The two passwords you entered do not match.")
                return
            self.result_username = username
            self.result_full_name = full_name
            self.result_role = role
            self.result_password = password
        else:
            self.result_username = username
            self.result_full_name = full_name
            self.result_role = role

        self.accept()


class _ResetPasswordDialog(QDialog):
    def __init__(self, parent, username: str):
        super().__init__(parent)
        self.setWindowTitle(f"Reset Password - {username}")
        self.setMinimumWidth(360)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("New password:", self.password_input)
        form.addRow("Confirm password:", self.confirm_input)

        save_button = QPushButton("Reset Password")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._on_save_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addWidget(save_button)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(buttons_row)
        self.setLayout(layout)

    def _on_save_clicked(self) -> None:
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        if len(password) < MIN_PASSWORD_LENGTH:
            QMessageBox.warning(
                self, "Password too short", f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
            )
            return
        if password != confirm:
            QMessageBox.warning(self, "Passwords don't match", "The two passwords you entered do not match.")
            return
        self.new_password = password
        self.accept()


class UsersPage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        title = QLabel("User Management")
        title.setObjectName("sectionLabel")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Username", "Full Name", "Role", "Status", "Last Login"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add User")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)

        self.reset_password_button = QPushButton("Reset Password")
        self.reset_password_button.clicked.connect(self._on_reset_password_clicked)

        self.toggle_active_button = QPushButton("Deactivate")
        self.toggle_active_button.clicked.connect(self._on_toggle_active_clicked)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.reset_password_button)
        buttons_row.addWidget(self.toggle_active_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        for user in list_users():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(user.username))
            self.table.setItem(row, 1, QTableWidgetItem(user.full_name))
            self.table.setItem(row, 2, QTableWidgetItem(ROLE_LABELS[user.role]))
            self.table.setItem(row, 3, QTableWidgetItem("Active" if user.is_active else "Inactive"))
            self.table.setItem(row, 4, QTableWidgetItem(user.last_login_at or "Never"))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, user.user_id)
        self._update_button_states()

    def _selected_user(self) -> Optional[User]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        user_id = self.table.item(selected[0].row(), 0).data(Qt.ItemDataRole.UserRole)
        for user in list_users():
            if user.user_id == user_id:
                return user
        return None

    def _update_button_states(self) -> None:
        user = self._selected_user()
        has_selection = user is not None
        self.edit_button.setEnabled(has_selection)
        self.reset_password_button.setEnabled(has_selection)
        self.toggle_active_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        if user is not None:
            self.toggle_active_button.setText("Reactivate" if not user.is_active else "Deactivate")

    def _on_add_clicked(self) -> None:
        dialog = _UserFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_user(
                username=dialog.result_username,
                full_name=dialog.result_full_name,
                plain_password=dialog.result_password,
                role=dialog.result_role,
                actor=self.current_user,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        dialog = _UserFormDialog(self, existing_user=user)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_user(
                user.user_id, dialog.result_username, dialog.result_full_name, dialog.result_role,
                actor=self.current_user,
            )
            self._refresh_table()

    def _on_reset_password_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            return
        dialog = _ResetPasswordDialog(self, user.username)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            reset_password(user.user_id, dialog.new_password, actor=self.current_user)
            QMessageBox.information(self, "Password reset", f"Password for '{user.username}' has been reset.")

    def _on_toggle_active_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            return

        if user.user_id == self.current_user.user_id:
            QMessageBox.warning(self, "Not allowed", "You cannot deactivate the account you're currently logged in as.")
            return

        making_inactive = user.is_active
        if making_inactive and user.role == "admin" and count_active_admins(exclude_user_id=user.user_id) == 0:
            QMessageBox.warning(
                self, "Can't deactivate last Administrator",
                "At least one active Administrator account must remain.",
            )
            return

        verb = "deactivate" if making_inactive else "reactivate"
        confirm = QMessageBox.question(
            self, f"Confirm {verb}", f"Are you sure you want to {verb} '{user.username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        set_user_active(user.user_id, not making_inactive, actor=self.current_user)
        self._refresh_table()

    def _on_delete_clicked(self) -> None:
        user = self._selected_user()
        if user is None:
            return

        if user.user_id == self.current_user.user_id:
            QMessageBox.warning(self, "Not allowed", "You cannot delete the account you're currently logged in as.")
            return

        if user.role == "admin" and count_active_admins(exclude_user_id=user.user_id) == 0:
            QMessageBox.warning(
                self, "Can't delete last Administrator",
                "At least one active Administrator account must remain.",
            )
            return

        confirm = QMessageBox.question(
            self, "Confirm delete",
            f"Are you sure you want to permanently delete '{user.username}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        delete_user(user.user_id, actor=self.current_user)
        self._refresh_table()
