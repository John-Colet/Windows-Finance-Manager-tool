"""Daily expenses: add/edit/delete, categories, receipts, tax tags."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QDate, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from app.models.category import (
    category_in_use, category_name_exists, create_category, delete_category,
    list_categories, rename_category,
)
from app.models.expense import (
    PAYMENT_METHODS, create_expense, delete_expense, get_receipt_image,
    list_expenses, update_expense,
)
from app.models.tax_tag import list_tax_tags
from app.models.user import User
from app.utils.dates import get_qt_display_format, iso_to_display, today_iso

MAX_RECEIPT_SIZE_BYTES = 8 * 1024 * 1024  # 8 MB, generous for a phone photo


class CategoryManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Categories")
        self.setMinimumWidth(360)

        self.list_widget = QListWidget()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Category name")

        add_button = QPushButton("Add")
        add_button.clicked.connect(self._on_add_clicked)
        rename_button = QPushButton("Rename Selected")
        rename_button.clicked.connect(self._on_rename_clicked)
        delete_button = QPushButton("Delete Selected")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._on_delete_clicked)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        add_row = QHBoxLayout()
        add_row.addWidget(self.name_input)
        add_row.addWidget(add_button)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(rename_button)
        buttons_row.addWidget(delete_button)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addLayout(add_row)
        layout.addLayout(buttons_row)
        layout.addWidget(close_button)
        self.setLayout(layout)

        self.categories_changed = False
        self._refresh()

    def _refresh(self) -> None:
        self.list_widget.clear()
        for category in list_categories():
            item = QListWidgetItem(category["name"])
            item.setData(1000, category["category_id"])
            self.list_widget.addItem(item)

    def _selected_category(self):
        item = self.list_widget.currentItem()
        if item is None:
            return None, None
        return item.data(1000), item.text()

    def _on_add_clicked(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a category name.")
            return
        if category_name_exists(name):
            QMessageBox.warning(self, "Already exists", "A category with that name already exists.")
            return
        create_category(name)
        self.name_input.clear()
        self.categories_changed = True
        self._refresh()

    def _on_rename_clicked(self) -> None:
        category_id, old_name = self._selected_category()
        if category_id is None:
            QMessageBox.information(self, "No selection", "Select a category first.")
            return
        new_name = self.name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Missing name", "Type the new name into the box, then click Rename Selected.")
            return
        if category_name_exists(new_name, exclude_id=category_id):
            QMessageBox.warning(self, "Already exists", "A category with that name already exists.")
            return
        rename_category(category_id, new_name)
        self.name_input.clear()
        self.categories_changed = True
        self._refresh()

    def _on_delete_clicked(self) -> None:
        category_id, name = self._selected_category()
        if category_id is None:
            QMessageBox.information(self, "No selection", "Select a category first.")
            return
        if category_in_use(category_id):
            QMessageBox.warning(
                self, "Category in use",
                f"'{name}' is used by one or more expenses and can't be deleted. "
                "Change those expenses to a different category first.",
            )
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", f"Delete category '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_category(category_id)
        self.categories_changed = True
        self._refresh()


class ExpenseFormDialog(QDialog):
    def __init__(self, parent=None, existing_expense=None):
        super().__init__(parent)
        self.existing_expense = existing_expense
        self.setWindowTitle("Edit Expense" if existing_expense else "Add Expense")
        self.setMinimumWidth(420)

        self.new_receipt_bytes: Optional[bytes] = None
        self.new_receipt_filename: Optional[str] = None
        self.remove_receipt_flag = False

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat(get_qt_display_format())
        self.date_edit.setDate(QDate.currentDate())

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("0.00")

        self.category_combo = QComboBox()
        self._category_ids: list[int] = []
        for category in list_categories():
            self.category_combo.addItem(category["name"])
            self._category_ids.append(category["category_id"])

        self.payment_combo = QComboBox()
        self.payment_combo.addItems(PAYMENT_METHODS)

        self.tax_tag_combo = QComboBox()
        self.tax_tag_combo.addItem("(None)")
        self._tax_tag_ids: list[Optional[int]] = [None]
        for tag in list_tax_tags():
            self.tax_tag_combo.addItem(tag["name"])
            self._tax_tag_ids.append(tag["tax_tag_id"])

        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(60)

        self.receipt_status_label = QLabel("No receipt attached.")
        attach_button = QPushButton("Attach Receipt...")
        attach_button.clicked.connect(self._on_attach_receipt)
        self.remove_receipt_button = QPushButton("Remove Receipt")
        self.remove_receipt_button.clicked.connect(self._on_remove_receipt)

        receipt_row = QHBoxLayout()
        receipt_row.addWidget(attach_button)
        receipt_row.addWidget(self.remove_receipt_button)

        form = QFormLayout()
        form.addRow("Date:", self.date_edit)
        form.addRow("Amount:", self.amount_input)
        form.addRow("Category:", self.category_combo)
        form.addRow("Payment method:", self.payment_combo)
        form.addRow("Tax tag:", self.tax_tag_combo)
        form.addRow("Notes:", self.notes_input)
        form.addRow("Receipt:", self.receipt_status_label)
        form.addRow("", receipt_row)

        if existing_expense is not None:
            self.date_edit.setDate(QDate.fromString(existing_expense.date, "yyyy-MM-dd"))
            self.amount_input.setText(f"{existing_expense.amount:.2f}")
            if existing_expense.category_id in self._category_ids:
                self.category_combo.setCurrentIndex(self._category_ids.index(existing_expense.category_id))
            if existing_expense.payment_method in PAYMENT_METHODS:
                self.payment_combo.setCurrentText(existing_expense.payment_method)
            if existing_expense.tax_tag_id in self._tax_tag_ids:
                self.tax_tag_combo.setCurrentIndex(self._tax_tag_ids.index(existing_expense.tax_tag_id))
            self.notes_input.setPlainText(existing_expense.notes)
            if existing_expense.has_receipt:
                self.receipt_status_label.setText(f"Attached: {existing_expense.receipt_filename or 'receipt'}")

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

    def _on_attach_receipt(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Receipt Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if not file_path:
            return
        path = Path(file_path)
        data = path.read_bytes()
        if len(data) > MAX_RECEIPT_SIZE_BYTES:
            QMessageBox.warning(self, "File too large", "Please choose an image smaller than 8 MB.")
            return
        self.new_receipt_bytes = data
        self.new_receipt_filename = path.name
        self.remove_receipt_flag = False
        self.receipt_status_label.setText(f"Attached: {path.name} (not saved yet)")

    def _on_remove_receipt(self) -> None:
        self.new_receipt_bytes = None
        self.new_receipt_filename = None
        self.remove_receipt_flag = True
        self.receipt_status_label.setText("No receipt attached.")

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
        if not self._category_ids:
            QMessageBox.warning(self, "No categories", "Please add at least one category first.")
            return

        self.result_date = self.date_edit.date().toString("yyyy-MM-dd")
        self.result_amount = amount
        self.result_category_id = self._category_ids[self.category_combo.currentIndex()]
        self.result_payment_method = self.payment_combo.currentText()
        self.result_tax_tag_id = self._tax_tag_ids[self.tax_tag_combo.currentIndex()]
        self.result_notes = self.notes_input.toPlainText().strip()
        self.accept()


class ExpensesPage(QWidget):
    def __init__(self, current_user: User):
        super().__init__()
        self.current_user = current_user

        title = QLabel("Expenses")
        title.setObjectName("sectionLabel")

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "Amount", "Category", "Payment Method", "Tax Tag", "Notes"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_button_states)

        add_button = QPushButton("Add Expense")
        add_button.setObjectName("primaryButton")
        add_button.clicked.connect(self._on_add_clicked)

        self.edit_button = QPushButton("Edit")
        self.edit_button.clicked.connect(self._on_edit_clicked)

        self.view_receipt_button = QPushButton("View Receipt")
        self.view_receipt_button.clicked.connect(self._on_view_receipt_clicked)

        self.delete_button = QPushButton("Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self._on_delete_clicked)

        manage_categories_button = QPushButton("Manage Categories")
        manage_categories_button.clicked.connect(self._on_manage_categories_clicked)

        self.total_label = QLabel("")

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(self.edit_button)
        buttons_row.addWidget(self.view_receipt_button)
        buttons_row.addWidget(self.delete_button)
        buttons_row.addWidget(manage_categories_button)
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
        expenses = list_expenses()
        total = 0.0
        for expense in expenses:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(iso_to_display(expense.date)))
            self.table.setItem(row, 1, QTableWidgetItem(f"{expense.amount:.2f}"))
            self.table.setItem(row, 2, QTableWidgetItem(expense.category_name))
            self.table.setItem(row, 3, QTableWidgetItem(expense.payment_method))
            self.table.setItem(row, 4, QTableWidgetItem(expense.tax_tag_name or ""))
            self.table.setItem(row, 5, QTableWidgetItem(expense.notes))
            self.table.item(row, 0).setData(1000, expense.expense_id)
            total += expense.amount
        self.total_label.setText(f"Total: {total:.2f}  ({len(expenses)} expense(s))")
        self._update_button_states()

    def _selected_expense_id(self) -> Optional[int]:
        selected = self.table.selectedItems()
        if not selected:
            return None
        return self.table.item(selected[0].row(), 0).data(1000)

    def _update_button_states(self) -> None:
        has_selection = self._selected_expense_id() is not None
        self.edit_button.setEnabled(has_selection)
        self.view_receipt_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _on_add_clicked(self) -> None:
        if not list_categories():
            QMessageBox.information(self, "No categories yet", "Add a category first using 'Manage Categories'.")
            return
        dialog = ExpenseFormDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            create_expense(
                user_id=self.current_user.user_id,
                date=dialog.result_date,
                amount=dialog.result_amount,
                category_id=dialog.result_category_id,
                payment_method=dialog.result_payment_method,
                notes=dialog.result_notes,
                tax_tag_id=dialog.result_tax_tag_id,
                receipt_image=dialog.new_receipt_bytes,
                receipt_filename=dialog.new_receipt_filename,
            )
            self._refresh_table()

    def _on_edit_clicked(self) -> None:
        from app.models.expense import get_expense

        expense_id = self._selected_expense_id()
        if expense_id is None:
            return
        expense = get_expense(expense_id)
        dialog = ExpenseFormDialog(self, existing_expense=expense)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_expense(
                expense_id,
                date=dialog.result_date,
                amount=dialog.result_amount,
                category_id=dialog.result_category_id,
                payment_method=dialog.result_payment_method,
                notes=dialog.result_notes,
                tax_tag_id=dialog.result_tax_tag_id,
                new_receipt_image=dialog.new_receipt_bytes,
                new_receipt_filename=dialog.new_receipt_filename,
                remove_receipt=dialog.remove_receipt_flag,
            )
            self._refresh_table()

    def _on_view_receipt_clicked(self) -> None:
        expense_id = self._selected_expense_id()
        if expense_id is None:
            return
        data = get_receipt_image(expense_id)
        if not data:
            QMessageBox.information(self, "No receipt", "This expense has no receipt attached.")
            return

        from app.models.expense import get_expense

        expense = get_expense(expense_id)
        suffix = Path(expense.receipt_filename or "receipt.png").suffix or ".png"
        temp_file = Path(tempfile.gettempdir()) / f"fm_receipt_{expense_id}{suffix}"
        temp_file.write_bytes(data)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(temp_file)))

    def _on_delete_clicked(self) -> None:
        expense_id = self._selected_expense_id()
        if expense_id is None:
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", "Are you sure you want to delete this expense? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_expense(expense_id)
        self._refresh_table()

    def _on_manage_categories_clicked(self) -> None:
        dialog = CategoryManagerDialog(self)
        dialog.exec()
        if dialog.categories_changed:
            self._refresh_table()
