"""Recurring bills: add/edit/delete, mark paid, in-app due/overdue reminders."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout, QWidget,
)

from app.models.bill import (
    FREQUENCIES, FREQUENCY_VALUES, create_bill, delete_bill, get_bill,
    list_bill_payments, list_bills, mark_bill_paid, update_bill,
)
from app.models.user import User
from app.utils.dates import get_qt_display_format, iso_to_display, today_iso

OVERDUE_COLOR = QColor("#fecaca")
DUE_SOON_COLOR = QColor("#fef3c7")


class BillFormDialog(QDialog):
    def __init__(self, parent=None, existing_bill=None):
        super().__init__(parent)
        self.existing_bill = existing_bill
        self.setWindowTitle("Edit Bill" if existing_bill else "Add Bill")
        self.setMinimumWidth(380)

        self.name_input = QLineEdit()
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat(get_qt_display_format())
        self.due_date_edit.setDate(QDate.currentDate())

        self.frequency_combo = QComboBox()
        self.frequency_combo.addItems(FREQUENCIES.values())
        self.frequency_combo.setCurrentText("Monthly")

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)

        form = QFormLayout()
        form.addRow("Bill name:", self.name_input)
        form.addRow("Amount:", self.amount_input)
        form.addRow("Due date:", self.due_date_edit)
        form.addRow("Frequency:", self.frequency_combo)
        form.addRow("Notes:", self.notes_input)

        if existing_bill is not None:
            self.name_input.setText(existing_bill.name)
            self.amount_input.setText(f"{existing_bill.amount:.2f}")
            self.due_date_edit.setDate(QDate.fromString(existing_bill.due_date, "yyyy-MM-dd"))
            self.frequency_combo.setCurrentText(FREQUENCIES[existing_bill.frequency])
            self.notes_input.setPlainText(existing_bill.notes)

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
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a bill name.")
            return
        try:
            amount = float(self.amount_input.text().strip().replace(",", ""))
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Please enter a valid number for the amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be greater than zero.")
            return

        self.result_name = name
        self.result_amount = amount
        self.result_due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        self.result_frequency = FREQUENCY_VALUES[self.frequency_combo.currentText()]
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class MarkPaidDialog(QDialog):
    def __init__(self, parent, bill_name: str, default_amount: float):
        super().__init__(parent)
        self.setWindowTitle(f"Mark Paid - {bill_name}")
        self.setMinimumWidth(340)

        self.paid_date_edit = QDateEdit()
        self.paid_date_edit.setCalendarPopup(True)
        self.paid_date_edit.setDisplayFormat(get_qt_display_format())
        self.paid_date_edit.setDate(QDate.currentDate())

        self.amount_input = QLineEdit()
        self.amount_input.setText(f"{default_amount:.2f}")

        form = QFormLayout()
        form.addRow("Date paid:", self.paid_date_edit)
        form.addRow("Amount paid:", self.amount_input)

        save_button = QPushButton("Mark Paid")
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
        try:
            amount = float(self.amount_input.text().strip().replace(",", ""))
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Please enter a valid number.")
            return
        self.result_paid_date = self.paid_date_edit.date().toString("yyyy-MM-dd")
        self.result_amount_paid = amount
        self.accept()


class PaymentHistoryDialog(QDialog):
    def __init__(self, parent, bill_name: str, bill_id: int):
        super().__init__(parent)
        self.setWindowTitle(f"Payment History - {bill_name}")
        self.setMinimumWidth(360)

        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Date Paid", "Amount Paid"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        for payment in list_bill_payments(bill_id):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(iso_to_display(payment["paid_date"])))
            table.setItem(row, 1, QTableWidgetItem(f"{payment['amount_paid']:.2f}"))

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(table)
        layout.addWidget(close_button)
        self.setLayout(layout)


class BillsPage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        title = QLabel("Recurring Bills")
        title.setObjectName("sectionLabel")

        self.reminder_label = QLabel("")
        self.reminder_label.setWordWrap(True)
        self.reminder_label.setObjectName("errorLabel")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Bill", "Amount", "Due Date", "Frequency", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add Bill")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)

        self.mark_paid_button = QPushButton("Mark Paid")
        self.mark_paid_button.clicked.connect(self._on_mark_paid_clicked)

        self.history_button = QPushButton("Payment History")
        self.history_button.clicked.connect(self._on_history_clicked)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.mark_paid_button)
        buttons_row.addWidget(self.history_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.reminder_label)
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        bills = list_bills()
        overdue_count = 0
        due_soon_count = 0
        for bill in bills:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(bill.name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{bill.amount:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(iso_to_display(bill.due_date)))
            self.table.setItem(row, 3, QTableWidgetItem(FREQUENCIES[bill.frequency]))

            if bill.is_overdue:
                status_text, color, overdue_count = "Overdue", OVERDUE_COLOR, overdue_count + 1
            elif bill.is_due_soon:
                status_text, color, due_soon_count = "Due soon", DUE_SOON_COLOR, due_soon_count + 1
            else:
                status_text, color = bill.status.capitalize(), None
            self.table.setItem(row, 4, QTableWidgetItem(status_text))

            if color is not None:
                for col in range(5):
                    self.table.item(row, col).setBackground(color)

            self.table.item(row, 0).setData(1000, bill.bill_id)

        messages = []
        if overdue_count:
            messages.append(f"{overdue_count} bill(s) overdue")
        if due_soon_count:
            messages.append(f"{due_soon_count} bill(s) due within {7} days")
        self.reminder_label.setText(" | ".join(messages))

        self._update_button_states()

    def _selected_bill_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return self.table.item(selected[0].row(), 0).data(1000)

    def _update_button_states(self) -> None:
        has_selection = self._selected_bill_id() is not None
        self.edit_button.setEnabled(has_selection)
        self.mark_paid_button.setEnabled(has_selection)
        self.history_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        dialog = BillFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_bill(
                self.current_user.user_id, dialog.result_name, dialog.result_amount,
                dialog.result_due_date, dialog.result_frequency, dialog.result_notes,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        dialog = BillFormDialog(self, existing_bill=bill)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_bill(
                bill_id, dialog.result_name, dialog.result_amount,
                dialog.result_due_date, dialog.result_frequency, dialog.result_notes,
            )
            self._refresh_table()

    def _on_mark_paid_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        dialog = MarkPaidDialog(self, bill.name, bill.amount)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mark_bill_paid(bill_id, dialog.result_paid_date, dialog.result_amount_paid)
            self._refresh_table()

    def _on_history_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        PaymentHistoryDialog(self, bill.name, bill_id).exec()

    def _on_delete_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm delete",
            "Are you sure you want to delete this bill and its payment history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_bill(bill_id)
        self._refresh_table()
