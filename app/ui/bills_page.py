"""Recurring bills: add/edit/delete, mark paid (optionally paying down a
debt), in-app due/overdue reminders, and one combined payment history for
every bill so you never have to click into bills one by one."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.bill import (
    INTERVAL_PRESETS, create_bill, delete_bill, format_frequency, get_bill,
    list_all_bill_payments, list_bill_payments, list_bills, mark_bill_paid, update_bill,
)
from app.models.debt import list_debts
from app.models.user import User
from app.ui.column_picker import ColumnPickerDialog, apply_column_visibility, get_visible_columns
from app.utils.dates import get_qt_display_format, iso_to_display

OVERDUE_COLOR = QColor("#fecaca")
DUE_SOON_COLOR = QColor("#fef3c7")

CUSTOM_LABEL = "Custom..."
_UNIT_OPTIONS = {"Days": "days", "Weeks": "weeks", "Months": "months"}


def _debt_options() -> list[tuple[str, Optional[int]]]:
    """(label, debt_id) pairs for a 'pay down a debt' dropdown, None = no link."""
    options: list[tuple[str, Optional[int]]] = [("(Not linked to a debt)", None)]
    for debt in list_debts():
        options.append((f"{debt.creditor_name} (balance {debt.balance:.2f})", debt.debt_id))
    return options


class BillFormDialog(QDialog):
    def __init__(self, parent=None, existing_bill=None):
        super().__init__(parent)
        self.existing_bill = existing_bill
        self.setWindowTitle("Edit Bill" if existing_bill else "Add Bill")
        self.setMinimumWidth(400)

        self.name_input = QLineEdit()
        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat(get_qt_display_format())
        self.due_date_edit.setDate(QDate.currentDate())

        self.preset_combo = QComboBox()
        for label, _unit, _count in INTERVAL_PRESETS:
            self.preset_combo.addItem(label)
        self.preset_combo.addItem(CUSTOM_LABEL)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

        self.custom_count_spin = QSpinBox()
        self.custom_count_spin.setRange(1, 365)
        self.custom_count_spin.setValue(1)
        self.custom_unit_combo = QComboBox()
        self.custom_unit_combo.addItems(_UNIT_OPTIONS.keys())

        custom_row = QHBoxLayout()
        custom_row.addWidget(QLabel("Every"))
        custom_row.addWidget(self.custom_count_spin)
        custom_row.addWidget(self.custom_unit_combo)
        self.custom_widget = QWidget()
        self.custom_widget.setLayout(custom_row)
        self.custom_widget.setVisible(False)

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)

        form = QFormLayout()
        form.addRow("Bill name:", self.name_input)
        form.addRow("Amount:", self.amount_input)
        form.addRow("Due date:", self.due_date_edit)
        form.addRow("Repeats:", self.preset_combo)
        form.addRow("", self.custom_widget)
        form.addRow("Notes:", self.notes_input)

        if existing_bill is not None:
            self.name_input.setText(existing_bill.name)
            self.amount_input.setText(f"{existing_bill.amount:.2f}")
            self.due_date_edit.setDate(QDate.fromString(existing_bill.due_date, "yyyy-MM-dd"))
            self._select_interval(existing_bill.interval_unit, existing_bill.interval_count)
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

    def _select_interval(self, interval_unit: str, interval_count: int) -> None:
        for label, unit, count in INTERVAL_PRESETS:
            if unit == interval_unit and count == interval_count:
                self.preset_combo.setCurrentText(label)
                return
        self.preset_combo.setCurrentText(CUSTOM_LABEL)
        self.custom_count_spin.setValue(interval_count)
        unit_label = {v: k for k, v in _UNIT_OPTIONS.items()}.get(interval_unit, "Months")
        self.custom_unit_combo.setCurrentText(unit_label)

    def _on_preset_changed(self, text: str) -> None:
        self.custom_widget.setVisible(text == CUSTOM_LABEL)

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

        preset_text = self.preset_combo.currentText()
        if preset_text == CUSTOM_LABEL:
            interval_count = self.custom_count_spin.value()
            interval_unit = _UNIT_OPTIONS[self.custom_unit_combo.currentText()]
        else:
            matching = [p for p in INTERVAL_PRESETS if p[0] == preset_text][0]
            _label, interval_unit, interval_count = matching

        self.result_name = name
        self.result_amount = amount
        self.result_due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        self.result_interval_unit = interval_unit
        self.result_interval_count = interval_count
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class MarkPaidDialog(QDialog):
    def __init__(self, parent, bill_name: str, default_amount: float):
        super().__init__(parent)
        self.setWindowTitle(f"Mark Paid - {bill_name}")
        self.setMinimumWidth(360)

        self.paid_date_edit = QDateEdit()
        self.paid_date_edit.setCalendarPopup(True)
        self.paid_date_edit.setDisplayFormat(get_qt_display_format())
        self.paid_date_edit.setDate(QDate.currentDate())

        self.amount_input = QLineEdit()
        self.amount_input.setText(f"{default_amount:.2f}")

        self.debt_combo = QComboBox()
        self._debt_options = _debt_options()
        for label, _debt_id in self._debt_options:
            self.debt_combo.addItem(label)

        form = QFormLayout()
        form.addRow("Date paid:", self.paid_date_edit)
        form.addRow("Amount paid:", self.amount_input)
        form.addRow("This pays down a debt:", self.debt_combo)

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
        self.result_linked_debt_id = self._debt_options[self.debt_combo.currentIndex()][1]
        self.accept()


class _CurrentBillsTab(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        self.reminder_label = QLabel("")
        self.reminder_label.setWordWrap(True)
        self.reminder_label.setObjectName("errorLabel")

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Bill", "Amount", "Due Date", "Repeats", "Status"])
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

        self.history_button = QPushButton("This Bill's History")
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
        layout.addWidget(self.reminder_label)
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
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
            self.table.setItem(row, 3, QTableWidgetItem(bill.frequency_label))

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
            messages.append(f"{due_soon_count} bill(s) due within 7 days")
        self.reminder_label.setText(" | ".join(messages))

        self._update_button_states()

    def _selected_bill_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        return self.table.item(selected[0].row(), 0).data(1000) if selected else None

    def _update_button_states(self) -> None:
        has_selection = self._selected_bill_id() is not None
        for button in (self.edit_button, self.mark_paid_button, self.history_button, self.delete_button):
            button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        dialog = BillFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_bill(
                self.current_user.user_id, dialog.result_name, dialog.result_amount,
                dialog.result_due_date, dialog.result_interval_unit, dialog.result_interval_count,
                dialog.result_notes,
            )
            self.refresh()

    def _on_edit_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        dialog = BillFormDialog(self, existing_bill=bill)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_bill(
                bill_id, dialog.result_name, dialog.result_amount, dialog.result_due_date,
                dialog.result_interval_unit, dialog.result_interval_count, dialog.result_notes,
            )
            self.refresh()

    def _on_mark_paid_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        dialog = MarkPaidDialog(self, bill.name, bill.amount)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mark_bill_paid(bill_id, dialog.result_paid_date, dialog.result_amount_paid, dialog.result_linked_debt_id)
            self.refresh()

    def _on_history_clicked(self) -> None:
        bill_id = self._selected_bill_id()
        if bill_id is None:
            return
        bill = get_bill(bill_id)
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Payment History - {bill.name}")
        dialog.setMinimumWidth(360)
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
        close_button.clicked.connect(dialog.accept)
        layout = QVBoxLayout()
        layout.addWidget(table)
        layout.addWidget(close_button)
        dialog.setLayout(layout)
        dialog.exec()

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
        self.refresh()


# Columns for the combined "all bills" history table.
_HISTORY_COLUMNS = [
    ("bill_name", "Bill"),
    ("paid_date", "Date Paid"),
    ("amount_paid", "Amount Paid"),
    ("linked_debt", "Paid Down Debt"),
]
_HISTORY_TABLE_KEY = "bills_history"


class _AllHistoryTab(QWidget):
    """One place to see every bill payment ever made, across all bills --
    no clicking into individual bills to piece the history together."""

    def __init__(self):
        super().__init__()

        columns_button = QPushButton("Columns...")
        columns_button.clicked.connect(self._on_columns_clicked)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Every bill payment you've ever recorded, newest first:"))
        top_row.addStretch()
        top_row.addWidget(columns_button)

        self.table = QTableWidget(0, len(_HISTORY_COLUMNS))
        self.table.setHorizontalHeaderLabels([label for _key, label in _HISTORY_COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.total_label = QLabel("")

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.table)
        layout.addWidget(self.total_label)
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
        self.table.setRowCount(0)
        total = 0.0
        for payment in list_all_bill_payments():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(payment["bill_name"]))
            self.table.setItem(row, 1, QTableWidgetItem(iso_to_display(payment["paid_date"])))
            self.table.setItem(row, 2, QTableWidgetItem(f"{payment['amount_paid']:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(payment["linked_debt_name"] or ""))
            total += payment["amount_paid"]
        self.total_label.setText(f"Total paid (all time): {total:.2f}")
        self._apply_column_visibility()

    def _apply_column_visibility(self) -> None:
        visible = get_visible_columns(_HISTORY_TABLE_KEY, _HISTORY_COLUMNS)
        apply_column_visibility(self.table, _HISTORY_COLUMNS, visible)

    def _on_columns_clicked(self) -> None:
        dialog = ColumnPickerDialog(self, _HISTORY_TABLE_KEY, _HISTORY_COLUMNS)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._apply_column_visibility()


class BillsPage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()

        title = QLabel("Recurring Bills")
        title.setObjectName("sectionLabel")

        self.current_tab = _CurrentBillsTab(current_user)
        self.history_tab = _AllHistoryTab()

        tabs = QTabWidget()
        tabs.addTab(self.current_tab, "Bills")
        tabs.addTab(self.history_tab, "Payment History (All Bills)")
        tabs.currentChanged.connect(self._on_tab_changed)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(tabs)
        self.setLayout(layout)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self.history_tab.refresh()
