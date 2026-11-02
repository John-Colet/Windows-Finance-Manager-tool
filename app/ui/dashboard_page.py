"""Dashboard: the home screen after login."""

from __future__ import annotations

from datetime import date

import matplotlib
matplotlib.use("QtAgg")

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.models.bill import FREQUENCIES, get_due_soon_or_overdue_bills
from app.models.debt import total_debt_balance, total_owed_to_me
from app.models.reports import get_monthly_trend, get_summary
from app.models.user import User
from app.utils.dates import iso_to_display

CHART_BACKGROUND = "#ffffff"


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


class DashboardPage(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user

        welcome = QLabel(f"Welcome, {user.full_name}!")
        welcome.setObjectName("welcomeLabel")

        self.income_card = _StatCard("Income This Month")
        self.expense_card = _StatCard("Expenses This Month")
        self.savings_card = _StatCard("Net Savings This Month")
        self.debt_card = _StatCard("Total Debt Remaining")
        self.owed_card = _StatCard("Money Owed To You")

        cards_row = QHBoxLayout()
        for card in (self.income_card, self.expense_card, self.savings_card, self.debt_card, self.owed_card):
            cards_row.addWidget(card)

        self.pie_figure = Figure(figsize=(4, 3))
        self.pie_canvas = FigureCanvasQTAgg(self.pie_figure)

        self.trend_figure = Figure(figsize=(5, 3))
        self.trend_canvas = FigureCanvasQTAgg(self.trend_figure)

        charts_row = QHBoxLayout()
        charts_row.addWidget(self.pie_canvas, stretch=1)
        charts_row.addWidget(self.trend_canvas, stretch=1)

        self.bills_label = QLabel("")
        self.bills_label.setWordWrap(True)
        self.bills_label.setObjectName("errorLabel")

        layout = QVBoxLayout()
        layout.addWidget(welcome)
        layout.addLayout(cards_row)
        layout.addLayout(charts_row)
        layout.addWidget(QLabel("Upcoming / Overdue Bills:"))
        layout.addWidget(self.bills_label)
        layout.addStretch()
        self.setLayout(layout)

        self.refresh()

    def refresh(self) -> None:
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        summary = get_summary(month_start, today.isoformat())

        self.income_card.set_value(f"{summary['total_income']:.2f}")
        self.expense_card.set_value(f"{summary['total_expenses']:.2f}")
        self.savings_card.set_value(f"{summary['net_savings']:.2f}")
        self.debt_card.set_value(f"{total_debt_balance():.2f}")
        self.owed_card.set_value(f"{total_owed_to_me():.2f}")

        self._draw_pie_chart(summary["expenses_by_category"])
        self._draw_trend_chart(get_monthly_trend(6))

        bills = get_due_soon_or_overdue_bills()
        if not bills:
            self.bills_label.setText("No bills due soon or overdue.")
        else:
            lines = []
            for bill in bills:
                tag = "OVERDUE" if bill.is_overdue else "due soon"
                lines.append(f"{bill.name}: {bill.amount:.2f} ({tag}, due {iso_to_display(bill.due_date)})")
            self.bills_label.setText("\n".join(lines))

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
