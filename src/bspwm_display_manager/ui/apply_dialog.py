from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def remaining_seconds(elapsed: int, timeout: int) -> int:
    return max(0, timeout - elapsed)


class ApplyConfirmDialog(QDialog):
    def __init__(self, timeout_seconds: int = 15, parent=None):
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self._elapsed = 0
        self._confirmed = False

        self.label = QLabel()
        self.keep_button = QPushButton("Keep these settings")
        self.revert_button = QPushButton("Revert now")
        self.keep_button.clicked.connect(self._confirm)
        self.revert_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.keep_button)
        buttons.addWidget(self.revert_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._update_label()

    def start(self) -> None:
        self._elapsed = 0
        self._timer.start()

    def _tick(self) -> None:
        self._elapsed += 1
        self._update_label()
        if remaining_seconds(self._elapsed, self.timeout_seconds) <= 0:
            self._timer.stop()
            self.reject()

    def _update_label(self) -> None:
        remaining = remaining_seconds(self._elapsed, self.timeout_seconds)
        self.label.setText(f"Keep these display settings? Reverting in {remaining}s.")

    def _confirm(self) -> None:
        self._confirmed = True
        self._timer.stop()
        self.accept()

    def was_confirmed(self) -> bool:
        return self._confirmed
