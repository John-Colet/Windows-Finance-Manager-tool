"""Income: add/edit/delete salary, side income, and other sources."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.income import (
    SOURCE_TYPE_VALUES, SOURCE_TYPES, create_income, delete_income, get_income,
    list_income, update_income,
)
from app.models.tax_tag import list_tax_tags
from app.models.user import User
from app.utils.dates import get_qt_display_format, iso_to_display


class IncomeFormDialog(QDialog):
    def __init__(self, parent=None, existing_income=None):
        super().__init__(parent)
        self.existing_income = existing_income
        self.setWindowTitle("Edit Income" if existing_income else "Add Income")
        self.setMinimumWidth(400)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(get_qt_display_format())
        self.date_edit.setDate(QDate.currentDate())

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")

        self.source_name_input = QLineEdit()
        self.source_name_input.setPlaceholderText("e.g. Employer name, client, etc.")

        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems(SOURCE_TYPES.values())

        self.taxable_checkbox = QCheckBox("This income is taxable")
        self.taxable_checkbox.setChecked(True)

        self.tax_tag_combo = QComboBox()
        self.tax_tag_combo.addItem("(None)")
        self._tax_tag_ids: list[Optional[int]] = [None]
        for tag in list_tax_tags():
            self.tax_tag_combo.addItem(tag["name"])
            self._tax_tag_ids.append(tag["tax_tag_id"])

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)

        form = QFormLayout()
        form.addRow("Date:", self.date_edit)
        form.addRow("Amount:", self.amount_input)
        form.addRow("Source:", self.source_name_input)
        form.addRow("Type:", self.source_type_combo)
        form.addRow("", self.taxable_checkbox)
        form.addRow("Tax tag:", self.tax_tag_combo)
        form.addRow("Notes:", self.notes_input)

        if existing_income is not None:
            self.date_edit.setDate(QDate.fromString(existing_income.date, "yyyy-MM-dd"))
            self.amount_input.setText(f"{existing_income.amount:.2f}")
            self.source_name_input.setText(existing_income.source_name)
            self.source_type_combo.setCurrentText(SOURCE_TYPES[existing_income.source_type])
            self.taxable_checkbox.setChecked(existing_income.is_taxable)
            if existing_income.tax_tag_id in self._tax_tag_ids:
                self.tax_tag_combo.setCurrentIndex(self._tax_tag_ids.index(existing_income.tax_tag_id))
            self.notes_input.setPlainText(existing_income.notes)

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
        amount_text = self.amount_input.text().strip().replace(",", "")
        try:
            amount = float(amount_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Please enter a valid number for the amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be greater than zero.")
            return
        source_name = self.source_name_input.text().strip()
        if not source_name:
            QMessageBox.warning(self, "Missing source", "Please enter where this income came from.")
            return

        self.result_date = self.date_edit.date().toString("yyyy-MM-dd")
        self.result_amount = amount
        self.result_source_name = source_name
        self.result_source_type = SOURCE_TYPE_VALUES[self.source_type_combo.currentText()]
        self.result_is_taxable = self.taxable_checkbox.isChecked()
        self.result_tax_tag_id = self._tax_tag_ids[self.tax_tag_combo.currentIndex()]
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class IncomePage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        title = QLabel("Income")
        title.setObjectName("sectionLabel")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Amount", "Source", "Type", "Taxable", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add Income")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        self.total_label = QLabel("")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addStretch()

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(buttons_row)
        layout.addWidget(self.table)
        layout.addWidget(self.total_label)
        self.setLayout(layout)

        self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(0)
        incomes = list_income()
        total = 0.0
        for income in incomes:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(iso_to_display(income.date)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{income.amount:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(income.source_name))
            self.table.setItem(row, 3, QTableWidgetItem(SOURCE_TYPES[income.source_type]))
            self.table.setItem(row, 4, QTableWidgetItem("Yes" if income.is_taxable else "No"))
            self.table.setItem(row, 5, QTableWidgetItem(income.notes))
            self.table.item(row, 0).setData(1000, income.income_id)
            total += income.amount
        self.total_label.setText(f"Total: {total:.2f}  ({len(incomes)} entrie(s))")
        self._update_button_states()

    def _selected_income_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return self.table.item(selected[0].row(), 0).data(1000)

    def _update_button_states(self) -> None:
        has_selection = self._selected_income_id() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        dialog = IncomeFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_income(
                user_id=self.current_user.user_id,
                date=dialog.result_date,
                amount=dialog.result_amount,
                source_name=dialog.result_source_name,
                source_type=dialog.result_source_type,
                is_taxable=dialog.result_is_taxable,
                notes=dialog.result_notes,
                tax_tag_id=dialog.result_tax_tag_id,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        income_id = self._selected_income_id()
        if income_id is None:
            return
        income = get_income(income_id)
        dialog = IncomeFormDialog(self, existing_income=income)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_income(
                income_id,
                date=dialog.result_date,
                amount=dialog.result_amount,
                source_name=dialog.result_source_name,
                source_type=dialog.result_source_type,
                is_taxable=dialog.result_is_taxable,
                notes=dialog.result_notes,
                tax_tag_id=dialog.result_tax_tag_id,
            )
            self._refresh_table()

    def _on_delete_clicked(self) -> None:
        income_id = self._selected_income_id()
        if income_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", "Are you sure you want to delete this income entry? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_income(income_id)
        self._refresh_table()
