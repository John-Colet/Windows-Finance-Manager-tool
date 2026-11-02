"""Shared stylesheets for the whole app: clean, modern, large buttons.

Two themes are provided (light/dark). apply_theme() swaps the whole app's
look instantly, with no restart needed.
"""

from PySide6.QtWidgets import QApplication

_SHARED_RULES = """
QPushButton {
    padding: 10px 18px;
    border-radius: 6px;
    min-height: 20px;
}

#primaryButton {
    background-color: #2563eb;
    color: white;
    font-weight: 600;
}

#primaryButton:hover {
    background-color: #1d4ed8;
}

#dangerButton {
    background-color: #dc2626;
    color: white;
    font-weight: 600;
}

#dangerButton:hover {
    background-color: #b91c1c;
}

#sidebarButton {
    background-color: #1f2937;
    color: #e5e7eb;
    margin: 4px 10px;
    text-align: left;
}

#sidebarButton:hover {
    background-color: #374151;
}

#logoutButton {
    background-color: #fee2e2;
    color: #b91c1c;
    margin: 4px 10px;
}

#logoutButton:hover {
    background-color: #fecaca;
}

#sidebar {
    background-color: #111827;
}

QListWidget#navList {
    background-color: #111827;
    color: #e5e7eb;
    border: none;
    font-size: 15px;
    outline: none;
}

QListWidget#navList::item {
    padding: 14px 20px;
}

QListWidget#navList::item:selected {
    background-color: #2563eb;
    color: white;
}

#titleLabel {
    font-size: 24px;
    font-weight: 600;
    padding: 10px;
}

#welcomeLabel {
    font-size: 20px;
    font-weight: 600;
    padding-bottom: 6px;
}

#sectionLabel {
    font-size: 17px;
    font-weight: 600;
    padding-top: 6px;
}

#placeholderLabel {
    font-size: 16px;
    color: #6b7280;
}

#errorLabel {
    color: #c0392b;
}

#successLabel {
    color: #15803d;
}

#statValueLabel {
    font-size: 22px;
    font-weight: 700;
}

#statCaptionLabel {
    font-size: 12px;
    color: #6b7280;
}
"""

LIGHT_STYLESHEET = (
    """
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    color: #1f2933;
}

QMainWindow, QDialog {
    background-color: #f5f7fa;
}

#creditLabel {
    font-size: 11px;
    color: #9aa5b1;
    padding: 8px;
}

QLineEdit, QComboBox {
    padding: 8px;
    border: 1px solid #d2d6dc;
    border-radius: 6px;
    background-color: white;
}

QPushButton {
    background-color: #e5e7eb;
    color: #1f2933;
}

QPushButton:hover {
    background-color: #d1d5db;
}

QTableWidget {
    background-color: white;
    border: 1px solid #d2d6dc;
    border-radius: 6px;
    gridline-color: #e5e7eb;
}

QHeaderView::section {
    background-color: #f0f2f5;
    padding: 6px;
    border: none;
    font-weight: 600;
}

#statCard {
    background-color: white;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 10px;
}
"""
    + _SHARED_RULES
)

DARK_STYLESHEET = (
    """
QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    color: #e5e7eb;
    background-color: #1f2430;
}

QMainWindow, QDialog {
    background-color: #1f2430;
}

#creditLabel {
    font-size: 11px;
    color: #8a93a3;
    padding: 8px;
}

QLineEdit, QComboBox {
    padding: 8px;
    border: 1px solid #3a4150;
    border-radius: 6px;
    background-color: #2a3140;
    color: #e5e7eb;
}

QPushButton {
    background-color: #3a4150;
    color: #e5e7eb;
}

QPushButton:hover {
    background-color: #4b5563;
}

QTableWidget {
    background-color: #2a3140;
    border: 1px solid #3a4150;
    border-radius: 6px;
    gridline-color: #3a4150;
    color: #e5e7eb;
}

QHeaderView::section {
    background-color: #1f2430;
    color: #e5e7eb;
    padding: 6px;
    border: none;
    font-weight: 600;
}

#statCard {
    background-color: #2a3140;
    border: 1px solid #3a4150;
    border-radius: 8px;
    padding: 10px;
}
"""
    + _SHARED_RULES
)

# Kept for Phase 1 compatibility (anything importing STYLESHEET still works).
STYLESHEET = LIGHT_STYLESHEET


def get_stylesheet(theme: str) -> str:
    return DARK_STYLESHEET if theme == "dark" else LIGHT_STYLESHEET


def apply_theme(theme: str) -> None:
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(get_stylesheet(theme))
