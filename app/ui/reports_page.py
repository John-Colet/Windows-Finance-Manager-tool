"""Reports: weekly/monthly/6-month/yearly summaries, with export."""

from __future__ import annotations

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.reports import get_period_range, get_summary
from app.utils.dates import get_qt_display_format
from app.utils.exporters import export_summary_to_csv, export_summary_to_excel, export_summary_to_pdf

PRESETS = ["This Week", "This Month", "Last 6 Months", "This Year", "Custom Range"]


class ReportsPage(QWidget):
    def __init__(self):
        super().__init__()

        title = QLabel("Reports")
        title.setObjectName("sectionLabel")

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat(get_qt_display_format())
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat(get_qt_display_format())
        self.start_date_edit.dateChanged.connect(self._on_custom_date_changed)
        self.end_date_edit.dateChanged.connect(self._on_custom_date_changed)

        export_csv_button = QPushButton("Export CSV")
        export_csv_button.clicked.connect(lambda: self._on_export_clicked("csv"))
        export_excel_button = QPushButton("Export Excel")
        export_excel_button.clicked.connect(lambda: self._on_export_clicked("excel"))
        export_pdf_button = QPushButton("Export PDF")
        export_pdf_button.clicked.connect(lambda: self._on_export_clicked("pdf"))

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Period:"))
        top_row.addWidget(self.preset_combo)
        top_row.addWidget(QLabel("From:"))
        top_row.addWidget(self.start_date_edit)
        top_row.addWidget(QLabel("To:"))
        top_row.addWidget(self.end_date_edit)
        top_row.addStretch()

        export_row = QHBoxLayout()
        export_row.addWidget(export_csv_button)
        export_row.addWidget(export_excel_button)
        export_row.addWidget(export_pdf_button)
        export_row.addStretch()

        self.summary_label = QLabel("")
        self.summary_label.setObjectName("welcomeLabel")

        self.category_table = QTableWidget(0, 2)
        self.category_table.setHorizontalHeaderLabels(["Category", "Total Spent"])
        self.category_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.category_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(top_row)
        layout.addWidget(self.summary_label)
        layout.addWidget(QLabel("Expenses by Category:"))
        layout.addWidget(self.category_table)
        layout.addLayout(export_row)
        self.setLayout(layout)

        self._updating = False
        self.preset_combo.setCurrentText("This Month")
        self._apply_preset("This Month")

    def _on_preset_changed(self, preset: str) -> None:
        is_custom = preset == "Custom Range"
        self.start_date_edit.setEnabled(is_custom)
        self.end_date_edit.setEnabled(is_custom)
        if not is_custom:
            self._apply_preset(preset)

    def _apply_preset(self, preset: str) -> None:
        start, end = get_period_range(preset)
        self._updating = True
        self.start_date_edit.setDate(QDate.fromString(start, "yyyy-MM-dd"))
        self.end_date_edit.setDate(QDate.fromString(end, "yyyy-MM-dd"))
        self._updating = False
        self._refresh_summary()

    def _on_custom_date_changed(self, _value) -> None:
        if not self._updating and self.preset_combo.currentText() == "Custom Range":
            self._refresh_summary()

    def _refresh_summary(self) -> None:
        start = self.start_date_edit.date().toString("yyyy-MM-dd")
        end = self.end_date_edit.date().toString("yyyy-MM-dd")
        summary = get_summary(start, end)
        self._last_summary = summary

        self.summary_label.setText(
            f"Income: {summary['total_income']:.2f}   |   "
            f"Expenses: {summary['total_expenses']:.2f}   |   "
            f"Net Savings: {summary['net_savings']:.2f}"
        )

        self.category_table.setRowCount(0)
        for row_data in summary["expenses_by_category"]:
            row = self.category_table.rowCount()
            self.category_table.insertRow(row)
            self.category_table.setItem(row, 0, QTableWidgetItem(row_data["category_name"]))
            self.category_table.setItem(row, 1, QTableWidgetItem(f"{row_data['total']:.2f}"))

    def _on_export_clicked(self, file_format: str) -> None:
        summary = self._last_summary
        extensions = {"csv": ("CSV Files (*.csv)", ".csv"), "excel": ("Excel Files (*.xlsx)", ".xlsx"), "pdf": ("PDF Files (*.pdf)", ".pdf")}
        filter_text, suffix = extensions[file_format]
        default_name = f"report_{summary['start_date']}_to_{summary['end_date']}{suffix}"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export Report", default_name, filter_text)
        if not file_path:
            return
        try:
            if file_format == "csv":
                export_summary_to_csv(summary, file_path)
            elif file_format == "excel":
                export_summary_to_excel(summary, file_path)
            else:
                export_summary_to_pdf(summary, file_path)
        except Exception as error:
            QMessageBox.critical(self, "Export failed", f"Could not export the report:\n{error}")
            return
        QMessageBox.information(self, "Export complete", f"Report saved to:\n{file_path}")
