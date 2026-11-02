"""Debts: money you owe, and money owed to you, in two tabs."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.debt import (
    DEBT_TYPE_VALUES, DEBT_TYPES, create_debt, create_loan, delete_debt, delete_loan,
    get_debt, get_loan, list_debt_payments, list_debts, list_loan_repayments, list_loans,
    record_debt_payment, record_loan_repayment, total_debt_balance, total_owed_to_me,
    update_debt, update_loan,
)
from app.models.user import User
from app.utils.dates import get_qt_display_format, iso_to_display


def _optional_date_or_none(date_edit: QDateEdit, checkbox_checked: bool) -> Optional[str]:
    return date_edit.date().toString("yyyy-MM-dd") if checkbox_checked else None


class DebtFormDialog(QDialog):
    def __init__(self, parent=None, existing_debt=None):
        super().__init__(parent)
        self.existing_debt = existing_debt
        self.setWindowTitle("Edit Debt" if existing_debt else "Add Debt")
        self.setMinimumWidth(400)

        self.creditor_input = QLineEdit()
        self.type_combo = QComboBox()
        self.type_combo.addItems(DEBT_TYPES.values())

        self.balance_input = QLineEdit()
        self.interest_rate_input = QLineEdit()
        self.interest_rate_input.setPlaceholderText("e.g. 19.99 (optional)")
        self.minimum_payment_input = QLineEdit()
        self.minimum_payment_input.setPlaceholderText("optional")

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat(get_qt_display_format())
        self.due_date_edit.setDate(QDate.currentDate())

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)

        form = QFormLayout()
        form.addRow("Creditor:", self.creditor_input)
        form.addRow("Type:", self.type_combo)
        form.addRow("Current balance:", self.balance_input)
        form.addRow("Interest rate (%):", self.interest_rate_input)
        form.addRow("Minimum payment:", self.minimum_payment_input)
        form.addRow("Next due date:", self.due_date_edit)
        form.addRow("Notes:", self.notes_input)

        if existing_debt is not None:
            self.creditor_input.setText(existing_debt.creditor_name)
            self.type_combo.setCurrentText(DEBT_TYPES[existing_debt.debt_type])
            self.balance_input.setText(f"{existing_debt.balance:.2f}")
            if existing_debt.interest_rate is not None:
                self.interest_rate_input.setText(str(existing_debt.interest_rate))
            if existing_debt.minimum_payment is not None:
                self.minimum_payment_input.setText(str(existing_debt.minimum_payment))
            if existing_debt.due_date:
                self.due_date_edit.setDate(QDate.fromString(existing_debt.due_date, "yyyy-MM-dd"))
            self.notes_input.setPlainText(existing_debt.notes)

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

    def _parse_optional_float(self, text: str) -> Optional[float]:
        text = text.strip()
        if not text:
            return None
        return float(text)

    def _on_save_clicked(self) -> None:
        creditor_name = self.creditor_input.text().strip()
        if not creditor_name:
            QMessageBox.warning(self, "Missing creditor", "Please enter who you owe this to.")
            return
        try:
            balance = float(self.balance_input.text().strip().replace(",", ""))
            interest_rate = self._parse_optional_float(self.interest_rate_input.text())
            minimum_payment = self._parse_optional_float(self.minimum_payment_input.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid number", "Please check the balance, interest rate, and minimum payment.")
            return
        if balance < 0:
            QMessageBox.warning(self, "Invalid balance", "Balance cannot be negative.")
            return

        self.result_creditor_name = creditor_name
        self.result_debt_type = DEBT_TYPE_VALUES[self.type_combo.currentText()]
        self.result_balance = balance
        self.result_interest_rate = interest_rate
        self.result_minimum_payment = minimum_payment
        self.result_due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class LoanFormDialog(QDialog):
    def __init__(self, parent=None, existing_loan=None):
        super().__init__(parent)
        self.existing_loan = existing_loan
        self.setWindowTitle("Edit Loan" if existing_loan else "Add Money Owed To Me")
        self.setMinimumWidth(380)

        self.debtor_input = QLineEdit()
        self.amount_input = QLineEdit()

        self.date_lent_edit = QDateEdit()
        self.date_lent_edit.setCalendarPopup(True)
        self.date_lent_edit.setDisplayFormat(get_qt_display_format())
        self.date_lent_edit.setDate(QDate.currentDate())

        self.due_date_edit = QDateEdit()
        self.due_date_edit.setCalendarPopup(True)
        self.due_date_edit.setDisplayFormat(get_qt_display_format())
        self.due_date_edit.setDate(QDate.currentDate())

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)

        form = QFormLayout()
        form.addRow("Who owes you:", self.debtor_input)
        form.addRow("Amount lent:", self.amount_input)
        form.addRow("Date lent:", self.date_lent_edit)
        form.addRow("Due date:", self.due_date_edit)
        form.addRow("Notes:", self.notes_input)

        if existing_loan is not None:
            self.debtor_input.setText(existing_loan.debtor_name)
            self.amount_input.setText(f"{existing_loan.amount:.2f}")
            self.date_lent_edit.setDate(QDate.fromString(existing_loan.date_lent, "yyyy-MM-dd"))
            if existing_loan.due_date:
                self.due_date_edit.setDate(QDate.fromString(existing_loan.due_date, "yyyy-MM-dd"))
            self.notes_input.setPlainText(existing_loan.notes)

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
        debtor_name = self.debtor_input.text().strip()
        if not debtor_name:
            QMessageBox.warning(self, "Missing name", "Please enter who owes you this money.")
            return
        try:
            amount = float(self.amount_input.text().strip().replace(",", ""))
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Please enter a valid number for the amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be greater than zero.")
            return

        self.result_debtor_name = debtor_name
        self.result_amount = amount
        self.result_date_lent = self.date_lent_edit.date().toString("yyyy-MM-dd")
        self.result_due_date = self.due_date_edit.date().toString("yyyy-MM-dd")
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class RecordPaymentDialog(QDialog):
    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(get_qt_display_format())
        self.date_edit.setDate(QDate.currentDate())

        self.amount_input = QLineEdit()

        form = QFormLayout()
        form.addRow("Date:", self.date_edit)
        form.addRow("Amount:", self.amount_input)

        save_button = QPushButton("Record Payment")
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
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be greater than zero.")
            return
        self.result_date = self.date_edit.date().toString("yyyy-MM-dd")
        self.result_amount = amount
        self.accept()


class HistoryDialog(QDialog):
    def __init__(self, parent, title: str, rows: list, date_key: str, amount_key: str):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(320)

        table = QTableWidget(0, 2)
        table.setHorizontalHeaderLabels(["Date", "Amount"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row_data in rows:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(iso_to_display(row_data[date_key])))
            table.setItem(row, 1, QTableWidgetItem(f"{row_data[amount_key]:.2f}"))

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        layout = QVBoxLayout()
        layout.addWidget(table)
        layout.addWidget(close_button)
        self.setLayout(layout)


class DebtsIOweTab(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Creditor", "Type", "Balance", "Interest Rate", "Min. Payment", "Next Due"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add Debt")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.pay_button = QPushButton("Record Payment")
        self.pay_button.clicked.connect(self._on_pay_clicked)
        self.history_button = QPushButton("Payment History")
        self.history_button.clicked.connect(self._on_history_clicked)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        self.total_label = QLabel("")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.pay_button)
        buttons_row.addWidget(self.history_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        layout.addWidget(self.total_label)
        self.setLayout(layout)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        for debt in list_debts():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(debt.creditor_name))
            self.table.setItem(row, 1, QTableWidgetItem(DEBT_TYPES[debt.debt_type]))
            self.table.setItem(row, 2, QTableWidgetItem(f"{debt.balance:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{debt.interest_rate:.2f}" if debt.interest_rate is not None else ""))
            self.table.setItem(row, 4, QTableWidgetItem(f"{debt.minimum_payment:.2f}" if debt.minimum_payment is not None else ""))
            self.table.setItem(row, 5, QTableWidgetItem(iso_to_display(debt.due_date) if debt.due_date else ""))
            self.table.item(row, 0).setData(1000, debt.debt_id)
        self.total_label.setText(f"Total debt remaining: {total_debt_balance():.2f}")
        self._update_button_states()

    def _selected_debt_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        return self.table.item(selected[0].row(), 0).data(1000) if selected else None

    def _update_button_states(self) -> None:
        has_selection = self._selected_debt_id() is not None
        for button in (self.edit_button, self.pay_button, self.history_button, self.delete_button):
            button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        dialog = DebtFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_debt(
                self.current_user.user_id, dialog.result_creditor_name, dialog.result_debt_type,
                dialog.result_balance, dialog.result_interest_rate, dialog.result_minimum_payment,
                dialog.result_due_date, dialog.result_notes,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        dialog = DebtFormDialog(self, existing_debt=get_debt(debt_id))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_debt(
                debt_id, dialog.result_creditor_name, dialog.result_debt_type, dialog.result_balance,
                dialog.result_interest_rate, dialog.result_minimum_payment, dialog.result_due_date,
                dialog.result_notes,
            )
            self._refresh_table()

    def _on_pay_clicked(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        dialog = RecordPaymentDialog(self, "Record Payment")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            record_debt_payment(debt_id, dialog.result_date, dialog.result_amount)
            self._refresh_table()

    def _on_history_clicked(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        rows = list_debt_payments(debt_id)
        HistoryDialog(self, "Payment History", rows, "payment_date", "amount").exec()

    def _on_delete_clicked(self) -> None:
        debt_id = self._selected_debt_id()
        if debt_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", "Delete this debt and its payment history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_debt(debt_id)
        self._refresh_table()


class MoneyOwedToMeTab(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Debtor", "Original Amount", "Outstanding", "Status", "Date Lent", "Due Date"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)
        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)
        self.pay_button = QPushButton("Record Repayment")
        self.pay_button.clicked.connect(self._on_pay_clicked)
        self.history_button = QPushButton("Repayment History")
        self.history_button.clicked.connect(self._on_history_clicked)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        self.total_label = QLabel("")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.pay_button)
        buttons_row.addWidget(self.history_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch()

        layout = QVBoxLayout()
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        layout.addWidget(self.total_label)
        self.setLayout(layout)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        for loan in list_loans():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(loan.debtor_name))
            self.table.setItem(row, 1, QTableWidgetItem(f"{loan.amount:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(f"{loan.outstanding_balance:.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(loan.status))
            self.table.setItem(row, 4, QTableWidgetItem(iso_to_display(loan.date_lent)))
            self.table.setItem(row, 5, QTableWidgetItem(iso_to_display(loan.due_date) if loan.due_date else ""))
            self.table.item(row, 0).setData(1000, loan.loan_id)
        self.total_label.setText(f"Total money owed to you: {total_owed_to_me():.2f}")
        self._update_button_states()

    def _selected_loan_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        return self.table.item(selected[0].row(), 0).data(1000) if selected else None

    def _update_button_states(self) -> None:
        has_selection = self._selected_loan_id() is not None
        for button in (self.edit_button, self.pay_button, self.history_button, self.delete_button):
            button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        dialog = LoanFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_loan(
                self.current_user.user_id, dialog.result_debtor_name, dialog.result_amount,
                dialog.result_date_lent, dialog.result_due_date, dialog.result_notes,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        loan_id = self._selected_loan_id()
        if loan_id is None:
            return
        dialog = LoanFormDialog(self, existing_loan=get_loan(loan_id))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_loan(
                loan_id, dialog.result_debtor_name, dialog.result_amount,
                dialog.result_date_lent, dialog.result_due_date, dialog.result_notes,
            )
            self._refresh_table()

    def _on_pay_clicked(self) -> None:
        loan_id = self._selected_loan_id()
        if loan_id is None:
            return
        dialog = RecordPaymentDialog(self, "Record Repayment")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            record_loan_repayment(loan_id, dialog.result_date, dialog.result_amount)
            self._refresh_table()

    def _on_history_clicked(self) -> None:
        loan_id = self._selected_loan_id()
        if loan_id is None:
            return
        rows = list_loan_repayments(loan_id)
        HistoryDialog(self, "Repayment History", rows, "repayment_date", "amount").exec()

    def _on_delete_clicked(self) -> None:
        loan_id = self._selected_loan_id()
        if loan_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", "Delete this record and its repayment history? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_loan(loan_id)
        self._refresh_table()


class DebtsPage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        title = QLabel("Debts")
        title.setObjectName("sectionLabel")

        tabs = QTabWidget()
        tabs.addTab(DebtsIOweTab(current_user), "Money I Owe")
        tabs.addTab(MoneyOwedToMeTab(current_user), "Money Owed To Me")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(tabs)
        self.setLayout(layout)
