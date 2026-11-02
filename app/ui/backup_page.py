"""Administrator-only: back up, restore, and wipe the database."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.models.settings import get_setting, set_setting
from app.utils.backup import create_backup, list_backups, restore_backup, wipe_database
from app.utils.dates import iso_to_display
from app.utils.paths import get_backups_dir, get_database_path

SCHEDULE_OPTIONS = {"none": "Off", "daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}
SCHEDULE_VALUES = {label: value for value, label in SCHEDULE_OPTIONS.items()}


class WipeConfirmDialog(QDialog):
    """Requires typing WIPE exactly, so this destructive action is never a misclick."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Database Wipe")
        self.setMinimumWidth(400)

        warning = QLabel(
            "This will PERMANENTLY delete every expense, income entry, bill, debt, user account, "
            "and setting in this database. This cannot be undone.\n\n"
            "If you want to keep a copy, back up first. To continue, type WIPE below."
        )
        warning.setWordWrap(True)
        warning.setObjectName("errorLabel")

        self.confirm_input = QLineEdit()
        self.confirm_input.textChanged.connect(self._on_text_changed)

        self.wipe_button = QPushButton("Wipe Everything")
        self.wipe_button.setObjectName("dangerButton")
        self.wipe_button.setEnabled(False)
        self.wipe_button.clicked.connect(self.accept)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(cancel_button)
        buttons_row.addWidget(self.wipe_button)

        layout = QVBoxLayout()
        layout.addWidget(warning)
        layout.addWidget(QLabel("Type WIPE to confirm:"))
        layout.addWidget(self.confirm_input)
        layout.addLayout(buttons_row)
        self.setLayout(layout)

    def _on_text_changed(self, text: str) -> None:
        self.wipe_button.setEnabled(text.strip() == "WIPE")


class BackupPage(QWidget):
    force_logout_requested = Signal()

    def __init__(self):
        super().__init__()

        title = QLabel("Backup & Restore")
        title.setObjectName("sectionLabel")

        self.db_path_label = QLabel(f"Database file: {get_database_path()}")
        self.db_path_label.setWordWrap(True)
        self.backups_folder_label = QLabel(f"Automatic backups folder: {get_backups_dir()}")
        self.backups_folder_label.setWordWrap(True)

        back_up_now_button = QPushButton("Back Up Now...")
        back_up_now_button.setObjectName("primaryButton")
        back_up_now_button.clicked.connect(self._on_back_up_now_clicked)

        self.schedule_combo = QComboBox()
        self.schedule_combo.addItems(SCHEDULE_OPTIONS.values())
        self.schedule_combo.setCurrentText(SCHEDULE_OPTIONS[get_setting("backup_schedule", "daily")])

        self.retention_input = QLineEdit()
        self.retention_input.setText(get_setting("backup_retention_count", "10"))

        save_schedule_button = QPushButton("Save Backup Schedule")
        save_schedule_button.clicked.connect(self._on_save_schedule_clicked)

        schedule_form = QFormLayout()
        schedule_form.addRow("Automatic backup frequency:", self.schedule_combo)
        schedule_form.addRow("Keep this many copies:", self.retention_input)

        self.backups_table = QTableWidget(0, 2)
        self.backups_table.setHorizontalHeaderLabels(["Backup File", "Created"])
        self.backups_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.backups_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.backups_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        restore_selected_button = QPushButton("Restore Selected Backup")
        restore_selected_button.clicked.connect(self._on_restore_selected_clicked)
        restore_from_file_button = QPushButton("Restore From Another File...")
        restore_from_file_button.clicked.connect(self._on_restore_from_file_clicked)

        restore_row = QHBoxLayout()
        restore_row.addWidget(restore_selected_button)
        restore_row.addWidget(restore_from_file_button)
        restore_row.addStretch()

        wipe_button = QPushButton("Wipe Database...")
        wipe_button.setObjectName("dangerButton")
        wipe_button.clicked.connect(self._on_wipe_clicked)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.db_path_label)
        layout.addWidget(self.backups_folder_label)
        layout.addWidget(back_up_now_button)
        layout.addLayout(schedule_form)
        layout.addWidget(save_schedule_button)
        layout.addWidget(QLabel("Automatic Backups:"))
        layout.addWidget(self.backups_table)
        layout.addLayout(restore_row)
        layout.addWidget(QLabel(""))
        layout.addWidget(wipe_button)
        self.setLayout(layout)

        self._refresh_backups_table()

    def _refresh_backups_table(self) -> None:
        self.backups_table.setRowCount(0)
        for backup_path in list_backups():
            row = self.backups_table.rowCount()
            self.backups_table.insertRow(row)
            self.backups_table.setItem(row, 0, QTableWidgetItem(backup_path.name))
            created = backup_path.stat().st_mtime
            from datetime import datetime
            self.backups_table.setItem(row, 1, QTableWidgetItem(iso_to_display(datetime.fromtimestamp(created).strftime("%Y-%m-%d"))))
            self.backups_table.item(row, 0).setData(1000, str(backup_path))

    def _on_back_up_now_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose Backup Destination")
        if not folder:
            return
        try:
            backup_path = create_backup(folder)
        except Exception as error:
            QMessageBox.critical(self, "Backup failed", f"Could not create the backup:\n{error}")
            return
        QMessageBox.information(self, "Backup complete", f"Backup saved to:\n{backup_path}")

    def _on_save_schedule_clicked(self) -> None:
        schedule_value = SCHEDULE_VALUES[self.schedule_combo.currentText()]
        try:
            retention = int(self.retention_input.text().strip())
            if retention < 1:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Invalid number", "Please enter a whole number of 1 or more.")
            return
        set_setting("backup_schedule", schedule_value)
        set_setting("backup_retention_count", str(retention))
        QMessageBox.information(self, "Saved", "Backup schedule settings saved.")

    def _confirm_and_restore(self, backup_file_path: str) -> None:
        confirm = QMessageBox.question(
            self, "Confirm restore",
            "This will REPLACE ALL current data with the contents of this backup. "
            "Anything added since that backup will be lost. This cannot be undone.\n\n"
            "You will be logged out afterward. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            restore_backup(backup_file_path)
        except Exception as error:
            QMessageBox.critical(self, "Restore failed", f"Could not restore this backup:\n{error}")
            return
        QMessageBox.information(self, "Restore complete", "The database has been restored. You will now be logged out.")
        self.force_logout_requested.emit()

    def _on_restore_selected_clicked(self) -> None:
        selected = self.backups_table.selectedItems()
        if not selected:
            QMessageBox.information(self, "No selection", "Select a backup from the list first.")
            return
        backup_file_path = self.backups_table.item(selected[0].row(), 0).data(1000)
        self._confirm_and_restore(backup_file_path)

    def _on_restore_from_file_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Choose Backup File", "", "Database Files (*.db);;All Files (*)")
        if not file_path:
            return
        self._confirm_and_restore(file_path)

    def _on_wipe_clicked(self) -> None:
        dialog = WipeConfirmDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                wipe_database()
            except Exception as error:
                QMessageBox.critical(self, "Wipe failed", f"Could not wipe the database:\n{error}")
                return
            QMessageBox.information(self, "Database wiped", "The database has been wiped. You will now be logged out.")
            self.force_logout_requested.emit()
