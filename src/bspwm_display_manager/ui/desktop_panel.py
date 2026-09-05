from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget,
)


class DesktopAssignmentPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._assignment: dict[str, list[str]] = {}

        self.monitor_combo = QComboBox()
        self.list_widget = QListWidget()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("desktop name")
        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")

        self.monitor_combo.currentTextChanged.connect(lambda _: self._refresh_list())
        self.add_button.clicked.connect(self._add_desktop)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))

        add_row = QHBoxLayout()
        add_row.addWidget(self.name_input)
        add_row.addWidget(self.add_button)
        button_row = QHBoxLayout()
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.up_button)
        button_row.addWidget(self.down_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.monitor_combo)
        layout.addWidget(self.list_widget)
        layout.addLayout(add_row)
        layout.addLayout(button_row)

    def set_monitors(self, names: list[str]) -> None:
        self.monitor_combo.clear()
        self.monitor_combo.addItems(names)

    def load_assignment(self, assignment: dict[str, list[str]]) -> None:
        self._assignment = {mon: list(names) for mon, names in assignment.items()}
        self._refresh_list()

    def assignment(self) -> dict[str, list[str]]:
        return {mon: list(names) for mon, names in self._assignment.items()}

    def _current_monitor(self) -> str | None:
        return self.monitor_combo.currentText() or None

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        mon = self._current_monitor()
        if mon is None:
            return
        for name in self._assignment.get(mon, []):
            self.list_widget.addItem(name)

    def _add_desktop(self) -> None:
        name = self.name_input.text().strip()
        mon = self._current_monitor()
        if not name or mon is None:
            return
        self._assignment.setdefault(mon, []).append(name)
        self.name_input.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        mon = self._current_monitor()
        row = self.list_widget.currentRow()
        if mon is None or row < 0:
            return
        del self._assignment[mon][row]
        self._refresh_list()

    def _move_selected(self, delta: int) -> None:
        mon = self._current_monitor()
        row = self.list_widget.currentRow()
        if mon is None or row < 0:
            return
        names = self._assignment[mon]
        new_row = row + delta
        if 0 <= new_row < len(names):
            names[row], names[new_row] = names[new_row], names[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(new_row)
