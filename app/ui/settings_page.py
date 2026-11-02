"""Settings screen: currency, date format, light/dark theme."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.models.settings import get_setting, set_setting
from app.ui.styles import apply_theme

CURRENCY_OPTIONS = ["CAD $", "USD $", "EUR €", "GBP £", "AUD $"]
DATE_FORMAT_OPTIONS = ["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"]
THEME_OPTIONS = {"Light": "light", "Dark": "dark"}
THEME_LABELS = {value: label for label, value in THEME_OPTIONS.items()}


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()

        title = QLabel("Settings")
        title.setObjectName("sectionLabel")

        self.currency_combo = QComboBox()
        self.currency_combo.setEditable(True)
        self.currency_combo.addItems(CURRENCY_OPTIONS)
        self.currency_combo.setCurrentText(get_setting("currency", "CAD $"))

        self.date_format_combo = QComboBox()
        self.date_format_combo.addItems(DATE_FORMAT_OPTIONS)
        self.date_format_combo.setCurrentText(get_setting("date_format", "YYYY-MM-DD"))

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(THEME_OPTIONS.keys())
        current_theme = get_setting("theme", "light")
        self.theme_combo.setCurrentText(THEME_LABELS.get(current_theme, "Light"))

        form = QFormLayout()
        form.addRow("Currency:", self.currency_combo)
        form.addRow("Date format:", self.date_format_combo)
        form.addRow("Theme:", self.theme_combo)

        self.status_label = QLabel("")
        self.status_label.setObjectName("successLabel")

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._on_save_clicked)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(form)
        layout.addWidget(save_button)
        layout.addWidget(self.status_label)
        layout.addStretch()
        self.setLayout(layout)

    def _on_save_clicked(self) -> None:
        currency = self.currency_combo.currentText().strip() or "CAD $"
        date_format = self.date_format_combo.currentText()
        theme_value = THEME_OPTIONS[self.theme_combo.currentText()]

        set_setting("currency", currency)
        set_setting("date_format", date_format)
        set_setting("theme", theme_value)
        apply_theme(theme_value)

        self.status_label.setText("Settings saved.")
