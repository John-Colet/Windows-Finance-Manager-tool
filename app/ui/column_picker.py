"""A reusable 'Columns...' button + dialog for show/hide column choices.

Each table that uses this passes a stable `table_key` (e.g. "expenses")
and its list of (column_key, column_label) pairs, in the same order they
appear in the QTableWidget. The chosen visible set is remembered in
Settings, per table, so it persists between sessions.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget,
)

from app.models.settings import get_setting, set_setting


def _setting_key(table_key: str) -> str:
    return f"columns_{table_key}"


def get_visible_columns(table_key: str, column_defs: list[tuple[str, str]]) -> set[str]:
    all_keys = [key for key, _label in column_defs]
    stored = get_setting(_setting_key(table_key), "")
    if not stored:
        return set(all_keys)
    visible = {key for key in stored.split(",") if key}
    # Never let every column be hidden by accident -- always show at least one.
    return visible if visible else set(all_keys)


def set_visible_columns(table_key: str, visible_keys: set[str]) -> None:
    set_setting(_setting_key(table_key), ",".join(sorted(visible_keys)))


def apply_column_visibility(table, column_defs: list[tuple[str, str]], visible_keys: set[str]) -> None:
    for index, (key, _label) in enumerate(column_defs):
        table.setColumnHidden(index, key not in visible_keys)


class ColumnPickerDialog(QDialog):
    def __init__(
        self, parent: QWidget, table_key: str, column_defs: list[tuple[str, str]],
        title: str = "Choose Columns",
    ):
        super().__init__(parent)
        self.table_key = table_key
        self.column_defs = column_defs
        self.setWindowTitle(title)
        self.setMinimumWidth(280)

        current_visible = get_visible_columns(table_key, column_defs)
        self.checkboxes: list[QCheckBox] = []

        layout = QVBoxLayout()
        for key, label in column_defs:
            checkbox = QCheckBox(label)
            checkbox.setChecked(key in current_visible)
            self.checkboxes.append(checkbox)
            layout.addWidget(checkbox)

        save_button = QPushButton("Save")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._on_save_clicked)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)

        buttons_row = QHBoxLayout()
        buttons_row.addWidget(cancel_button)
        buttons_row.addWidget(save_button)

        layout.addLayout(buttons_row)
        self.setLayout(layout)

    def _on_save_clicked(self) -> None:
        visible_keys = {
            key for (key, _label), checkbox in zip(self.column_defs, self.checkboxes) if checkbox.isChecked()
        }
        if not visible_keys:
            visible_keys = {self.column_defs[0][0]}  # never allow zero columns
        set_visible_columns(self.table_key, visible_keys)
        self.accept()
