from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from bspwm_display_manager.backend.models import Output
from bspwm_display_manager.backend.scale import suggest_global_scale

_CHOICES = [100, 125, 150, 175, 200]


class SessionScaleControl(QWidget):
    def __init__(self):
        super().__init__()
        self.combo = QComboBox()
        for pct in _CHOICES:
            self.combo.addItem(f"{pct}%", pct)
        layout = QFormLayout(self)
        layout.addRow("Session scale", self.combo)

    def set_outputs(self, outputs: list[Output]) -> None:
        suggested = suggest_global_scale(outputs)
        idx = self.combo.findData(suggested)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def value(self) -> int:
        return self.combo.currentData()
