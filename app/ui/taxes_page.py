"""Tax tags and a yearly tax summary to hand to your accountant.

This page only tags and totals your numbers -- it does not decide what
is actually tax-deductible. Always confirm with your accountant or the
CRA before filing.
"""

from __future__ import annotations

import csv
from datetime import date

from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.reports import get_available_years, get_yearly_tax_summary
from app.models.tax_tag import (
    create_tax_tag, delete_tax_tag, list_tax_tags, tax_tag_in_use,
    tax_tag_name_exists, update_tax_tag,
)


class TaxTagManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Tax Tags")
        self.setMinimumWidth(420)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Tag name")
        self.description_input = QLineEdit()
        self.description_input.setPlaceholderText("Description (optional)")

        add_button = QPushButton("Add")
        add_button.clicked.connect(self._on_add_clicked)
        save_button = QPushButton("Save Changes to Selected")
        save_button.clicked.connect(self._on_save_clicked)
        delete_button = QPushButton("Delete Selected")
        delete_button.setObjectName("dangerButton")
        delete_button.clicked.connect(self._on_delete_clicked)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(add_button)
        buttons_row.addWidget(save_button)
        buttons_row.addWidget(delete_button)

        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        layout.addWidget(self.name_input)
        layout.addWidget(self.description_input)
        layout.addLayout(buttons_row)
        layout.addWidget(close_button)
        self.setLayout(layout)

        self.tags_changed = False
        self._refresh()

    def _refresh(self) -> None:
        self.list_widget.clear()
        for tag in list_tax_tags():
            item = QListWidgetItem(tag["name"])
            item.setData(1000, tag["tax_tag_id"])
            item.setData(1001, tag["description"] or "")
            self.list_widget.addItem(item)

    def _on_selection_changed(self, current, _previous) -> None:
        if current is None:
            return
        self.name_input.setText(current.text())
        self.description_input.setText(current.data(1001) or "")

    def _on_add_clicked(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a tag name.")
            return
        if tax_tag_name_exists(name):
            QMessageBox.warning(self, "Already exists", "A tax tag with that name already exists.")
            return
        create_tax_tag(name, self.description_input.text().strip())
        self.tags_changed = True
        self._refresh()

    def _on_save_clicked(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Select a tag first.")
            return
        tax_tag_id = item.data(1000)
        new_name = self.name_input.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Missing name", "Please enter a tag name.")
            return
        if tax_tag_name_exists(new_name, exclude_id=tax_tag_id):
            QMessageBox.warning(self, "Already exists", "A tax tag with that name already exists.")
            return
        update_tax_tag(tax_tag_id, new_name, self.description_input.text().strip())
        self.tags_changed = True
        self._refresh()

    def _on_delete_clicked(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            QMessageBox.information(self, "No selection", "Select a tag first.")
            return
        tax_tag_id = item.data(1000)
        if tax_tag_in_use(tax_tag_id):
            QMessageBox.warning(
                self, "Tag in use",
                "This tag is used by one or more expenses/income entries and can't be deleted.",
            )
            return
        confirm = QMessageBox.question(
            self, "Confirm delete", f"Delete tag '{item.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_tax_tag(tax_tag_id)
        self.tags_changed = True
        self._refresh()


class TaxesPage(QWidget):
    def __init__(self):
        super().__init__()

        title = QLabel("Yearly Tax Summary")
        title.setObjectName("sectionLabel")

        disclaimer = QLabel(
            "This summarizes your tagged expenses and income by year. It does not determine what is "
            "actually tax-deductible -- please confirm with your accountant or the CRA."
        )
        disclaimer.setWordWrap(True)
        disclaimer.setObjectName("placeholderLabel")

        self.year_combo = QComboBox()
        self.year_combo.setEditable(True)
        self.year_combo.currentTextChanged.connect(self._on_year_changed)

        manage_tags_button = QPushButton("Manage Tax Tags")
        manage_tags_button.clicked.connect(self._on_manage_tags_clicked)

        export_button = QPushButton("Export Summary to CSV")
        export_button.clicked.connect(self._on_export_clicked)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Year:"))
        top_row.addWidget(self.year_combo)
        top_row.addWidget(manage_tags_button)
        top_row.addWidget(export_button)
        top_row.addStretch()

        self.expense_table = QTableWidget(0, 3)
        self.expense_table.setHorizontalHeaderLabels(["Tax Tag", "Total Expenses", "# of Expenses"])
        self.expense_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.expense_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.income_table = QTableWidget(0, 3)
        self.income_table.setHorizontalHeaderLabels(["Tax Tag", "Total Income", "# of Entries"])
        self.income_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.income_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.totals_label = QLabel("")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(disclaimer)
        layout.addLayout(top_row)
        layout.addWidget(QLabel("Tagged Expenses by Tax Tag:"))
        layout.addWidget(self.expense_table)
        layout.addWidget(QLabel("Tagged Income by Tax Tag:"))
        layout.addWidget(self.income_table)
        layout.addWidget(self.totals_label)
        self.setLayout(layout)

        self._populate_years()

    def _populate_years(self) -> None:
        years = get_available_years()
        current_year = date.today().year
        if current_year not in years:
            years.append(current_year)
        years = sorted(set(years))
        self.year_combo.blockSignals(True)
        self.year_combo.clear()
        self.year_combo.addItems([str(y) for y in years])
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.blockSignals(False)
        self._refresh_summary()

    def _on_year_changed(self, _text: str) -> None:
        self._refresh_summary()

    def _current_year(self) -> int:
        try:
            return int(self.year_combo.currentText())
        except ValueError:
            return date.today().year

    def _refresh_summary(self) -> None:
        year = self._current_year()
        summary = get_yearly_tax_summary(year)

        self.expense_table.setRowCount(0)
        for row_data in summary["expenses_by_tag"]:
            row = self.expense_table.rowCount()
            self.expense_table.insertRow(row)
            self.expense_table.setItem(row, 0, QTableWidgetItem(row_data["tax_tag_name"]))
            self.expense_table.setItem(row, 1, QTableWidgetItem(f"{row_data['total']:.2f}"))
            self.expense_table.setItem(row, 2, QTableWidgetItem(str(row_data["count"])))

        self.income_table.setRowCount(0)
        for row_data in summary["income_by_tag"]:
            row = self.income_table.rowCount()
            self.income_table.insertRow(row)
            self.income_table.setItem(row, 0, QTableWidgetItem(row_data["tax_tag_name"]))
            self.income_table.setItem(row, 1, QTableWidgetItem(f"{row_data['total']:.2f}"))
            self.income_table.setItem(row, 2, QTableWidgetItem(str(row_data["count"])))

        self.totals_label.setText(
            f"Total tagged expenses: {summary['total_tagged_expenses']:.2f}   |   "
            f"Taxable income: {summary['taxable_income_total']:.2f}   |   "
            f"Non-taxable income: {summary['non_taxable_income_total']:.2f}"
        )
        self._last_summary = summary

    def _on_manage_tags_clicked(self) -> None:
        dialog = TaxTagManagerDialog(self)
        dialog.exec()
        if dialog.tags_changed:
            self._refresh_summary()

    def _on_export_clicked(self) -> None:
        summary = self._last_summary
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Tax Summary", f"tax_summary_{summary['year']}.csv", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        with open(file_path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([f"Tax Summary for {summary['year']}"])
            writer.writerow([])
            writer.writerow(["Tagged Expenses by Tax Tag"])
            writer.writerow(["Tax Tag", "Total", "Count"])
            for row_data in summary["expenses_by_tag"]:
                writer.writerow([row_data["tax_tag_name"], f"{row_data['total']:.2f}", row_data["count"]])
            writer.writerow([])
            writer.writerow(["Tagged Income by Tax Tag"])
            writer.writerow(["Tax Tag", "Total", "Count"])
            for row_data in summary["income_by_tag"]:
                writer.writerow([row_data["tax_tag_name"], f"{row_data['total']:.2f}", row_data["count"]])
            writer.writerow([])
            writer.writerow(["Total Tagged Expenses", f"{summary['total_tagged_expenses']:.2f}"])
            writer.writerow(["Total Taxable Income", f"{summary['taxable_income_total']:.2f}"])
            writer.writerow(["Total Non-Taxable Income", f"{summary['non_taxable_income_total']:.2f}"])
        QMessageBox.information(self, "Export complete", f"Tax summary saved to:\n{file_path}")
