"""Dashboard: the home screen after login, with widgets you can show or hide."""

from __future__ import annotations

from datetime import date

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from app.models.bill import get_upcoming_bills, list_all_bill_payments
from app.models.debt import get_debt_payoff_progress, total_debt_balance, total_owed_to_me
from app.models.reports import get_cash_balance, get_cumulative_savings_trend, get_monthly_trend, get_summary
from app.models.user import User
from app.ui.column_picker import ColumnPickerDialog, get_visible_columns, set_visible_columns
from app.utils.dates import iso_to_display

DASHBOARD_WIDGETS_KEY = "dashboard_widgets"

WIDGET_DEFS = [
    ("cash_card", "Cash & Bank Balance"),
    ("income_card", "Income This Month"),
    ("expense_card", "Expenses This Month"),
    ("savings_card", "Net Savings This Month"),
    ("debt_card", "Total Debt Remaining"),
    ("owed_card", "Money Owed To You"),
    ("category_pie", "Spending by Category (chart)"),
    ("trend_chart", "Income vs Expenses, 6 Months (chart)"),
    ("savings_trend_chart", "Net Worth Trend, 6 Months (chart)"),
    ("upcoming_bills", "Upcoming Bills"),
    ("recent_payments", "Recently Paid Bills"),
    ("debt_progress", "Debt Payoff Progress"),
]


class _StatCard(QWidget):
    def __init__(self, label_text: str):
        super().__init__()
        self.setObjectName("statCard")
        self.value_label = QLabel("0.00")
        self.value_label.setObjectName("statValueLabel")
        caption = QLabel(label_text)
        caption.setObjectName("statCaptionLabel")
        layout = QVBoxLayout()
        layout.addWidget(self.value_label)
        layout.addWidget(caption)
        self.setLayout(layout)

    def set_value(self, text: str) -> None:
        self.value_label.setText(text)


class _ListCard(QWidget):
    """A small card showing a short labelled list of text lines."""

    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("statCard")
        title_label = QLabel(title)
        title_label.setObjectName("statCaptionLabel")
        self.body_label = QLabel("")
        self.body_label.setWordWrap(True)
        layout = QVBoxLayout()
        layout.addWidget(title_label)
        layout.addWidget(self.body_label)
        layout.addStretch()
        self.setLayout(layout)

    def set_lines(self, lines: list[str], empty_text: str) -> None:
        self.body_label.setText("\n".join(lines) if lines else empty_text)


class DashboardPage(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user

        welcome = QLabel(f"Welcome, {user.full_name}!")
        welcome.setObjectName("welcomeLabel")

        customize_button = QPushButton("Customize Dashboard...")
        customize_button.clicked.connect(self._on_customize_clicked)

        header_row = QHBoxLayout()
        header_row.addWidget(welcome)
        header_row.addStretch()
        header_row.addWidget(customize_button)

        self.cash_card = _StatCard("Cash & Bank Balance")
        self.income_card = _StatCard("Income This Month")
        self.expense_card = _StatCard("Expenses This Month")
        self.savings_card = _StatCard("Net Savings This Month")
        self.debt_card = _StatCard("Total Debt Remaining")
        self.owed_card = _StatCard("Money Owed To You")
        self._cards = {
            "cash_card": self.cash_card, "income_card": self.income_card, "expense_card": self.expense_card,
            "savings_card": self.savings_card, "debt_card": self.debt_card, "owed_card": self.owed_card,
        }
        self.cards_row = QHBoxLayout()

        self.pie_figure = Figure(figsize=(4, 3))
        self.pie_canvas = FigureCanvasQTAgg(self.pie_figure)
        self.trend_figure = Figure(figsize=(4, 3))
        self.trend_canvas = FigureCanvasQTAgg(self.trend_figure)
        self.savings_trend_figure = Figure(figsize=(4, 3))
        self.savings_trend_canvas = FigureCanvasQTAgg(self.savings_trend_figure)
        self.charts_row = QHBoxLayout()

        self.upcoming_bills_card = _ListCard("Upcoming Bills")
        self.recent_payments_card = _ListCard("Recently Paid Bills")
        self.debt_progress_card = _ListCard("Debt Payoff Progress")
        self.lists_row = QHBoxLayout()

        self.layout_container = QVBoxLayout()
        self.layout_container.addLayout(header_row)
        self.layout_container.addLayout(self.cards_row)
        self.layout_container.addLayout(self.charts_row)
        self.layout_container.addLayout(self.lists_row)
        self.layout_container.addStretch()
        self.setLayout(self.layout_container)

        self.refresh()

    def _enabled_widgets(self) -> set[str]:
        return get_visible_columns(DASHBOARD_WIDGETS_KEY, WIDGET_DEFS)

    def _on_customize_clicked(self) -> None:
        dialog = ColumnPickerDialog(self, DASHBOARD_WIDGETS_KEY, WIDGET_DEFS, title="Customize Dashboard")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def refresh(self) -> None:
        enabled = self._enabled_widgets()

        today = date.today()
        month_start = today.replace(day=1).isoformat()
        summary = get_summary(month_start, today.isoformat())

        self.cash_card.set_value(f"{get_cash_balance():.2f}")
        self.income_card.set_value(f"{summary['total_income']:.2f}")
        self.expense_card.set_value(f"{summary['total_expenses']:.2f}")
        self.savings_card.set_value(f"{summary['net_savings']:.2f}")
        self.debt_card.set_value(f"{total_debt_balance():.2f}")
        self.owed_card.set_value(f"{total_owed_to_me():.2f}")

        self._rebuild_row(self.cards_row, [
            (key, self._cards[key]) for key in
            ["cash_card", "income_card", "expense_card", "savings_card", "debt_card", "owed_card"]
            if key in enabled
        ])

        chart_widgets = []
        if "category_pie" in enabled:
            self._draw_pie_chart(summary["expenses_by_category"])
            chart_widgets.append(("category_pie", self.pie_canvas))
        if "trend_chart" in enabled:
            self._draw_trend_chart(get_monthly_trend(6))
            chart_widgets.append(("trend_chart", self.trend_canvas))
        if "savings_trend_chart" in enabled:
            self._draw_savings_trend_chart(get_cumulative_savings_trend(6))
            chart_widgets.append(("savings_trend_chart", self.savings_trend_canvas))
        self._rebuild_row(self.charts_row, chart_widgets)

        if "upcoming_bills" in enabled:
            upcoming = get_upcoming_bills(5)
            lines = [
                f"{bill.name}: {bill.amount:.2f} (due {iso_to_display(bill.due_date)}"
                f"{', OVERDUE' if bill.is_overdue else ''})"
                for bill in upcoming
            ]
            self.upcoming_bills_card.set_lines(lines, "No upcoming bills.")

        if "recent_payments" in enabled:
            recent = list_all_bill_payments()[:5]
            lines = [
                f"{p['bill_name']}: {p['amount_paid']:.2f} on {iso_to_display(p['paid_date'])}"
                for p in recent
            ]
            self.recent_payments_card.set_lines(lines, "No bills paid yet.")

        if "debt_progress" in enabled:
            progress = get_debt_payoff_progress()
            lines = [
                f"{row['creditor_name']}: {row['percent_paid']:.0f}% paid off "
                f"(balance {row['balance']:.2f})"
                for row in progress
            ]
            self.debt_progress_card.set_lines(lines, "No debts on file.")

        self._rebuild_row(self.lists_row, [
            (key, widget) for key, widget in
            [("upcoming_bills", self.upcoming_bills_card), ("recent_payments", self.recent_payments_card),
             ("debt_progress", self.debt_progress_card)]
            if key in enabled
        ])

    def _rebuild_row(self, row_layout: QHBoxLayout, items: list[tuple[str, QWidget]]) -> None:
        while row_layout.count():
            item = row_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        for _key, widget in items:
            row_layout.addWidget(widget, stretch=1)

    def _draw_pie_chart(self, expenses_by_category: list[dict]) -> None:
        self.pie_figure.clear()
        axes = self.pie_figure.add_subplot(111)
        if not expenses_by_category:
            axes.text(0.5, 0.5, "No expenses this month", ha="center", va="center")
            axes.axis("off")
        else:
            labels = [row["category_name"] for row in expenses_by_category]
            values = [row["total"] for row in expenses_by_category]
            axes.pie(values, labels=labels, autopct="%1.0f%%", wedgeprops={"width": 0.4})
            axes.set_title("Spending by Category")
        self.pie_figure.tight_layout()
        self.pie_canvas.draw()

    def _draw_trend_chart(self, trend: list[dict]) -> None:
        self.trend_figure.clear()
        axes = self.trend_figure.add_subplot(111)
        labels = [row["label"] for row in trend]
        income_values = [row["income"] for row in trend]
        expense_values = [row["expense"] for row in trend]
        x_positions = range(len(labels))
        axes.bar([x - 0.2 for x in x_positions], income_values, width=0.4, label="Income", color="#2563eb")
        axes.bar([x + 0.2 for x in x_positions], expense_values, width=0.4, label="Expenses", color="#dc2626")
        axes.set_xticks(list(x_positions))
        axes.set_xticklabels(labels, rotation=45, ha="right")
        axes.set_title("Income vs Expenses (Last 6 Months)")
        axes.legend()
        self.trend_figure.tight_layout()
        self.trend_canvas.draw()

    def _draw_savings_trend_chart(self, trend: list[dict]) -> None:
        self.savings_trend_figure.clear()
        axes = self.savings_trend_figure.add_subplot(111)
        labels = [row["label"] for row in trend]
        values = [row["cumulative"] for row in trend]
        x_positions = range(len(labels))
        axes.plot(list(x_positions), values, marker="o", color="#2563eb")
        axes.axhline(0, color="#9ca3af", linewidth=0.8)
        axes.set_xticks(list(x_positions))
        axes.set_xticklabels(labels, rotation=45, ha="right")
        axes.set_title("Net Worth Trend (Cumulative Savings)")
        self.savings_trend_figure.tight_layout()
        self.savings_trend_canvas.draw()
