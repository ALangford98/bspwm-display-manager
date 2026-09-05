from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QWidget,
)

from bspwm_display_manager.backend.models import Output


class OutputPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.output: Output | None = None  # public: main_window reads this
        # to know which output the panel's current edits apply to.
        self.mode_combo = QComboBox()
        self.rate_combo = QComboBox()
        self.primary_checkbox = QCheckBox("Primary")
        self.blurry_scale_checkbox = QCheckBox("Enable per-output scale (blurry)")
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 2.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setVisible(False)
        self.blurry_scale_checkbox.toggled.connect(self.scale_spin.setVisible)
        self.mode_combo.currentIndexChanged.connect(self._refresh_rate_choices)

        layout = QFormLayout(self)
        layout.addRow("Mode", self.mode_combo)
        layout.addRow("Refresh rate", self.rate_combo)
        layout.addRow(self.primary_checkbox)
        layout.addRow(self.blurry_scale_checkbox)
        layout.addRow("Per-output scale", self.scale_spin)

    def set_output(self, output: Output) -> None:
        self.output = output
        self.mode_combo.clear()
        seen_resolutions: list[tuple[int, int]] = []
        for mode in output.modes:
            res = (mode.width, mode.height)
            if res not in seen_resolutions:
                seen_resolutions.append(res)
                self.mode_combo.addItem(f"{mode.width}x{mode.height}", res)
        current = output.current_mode()
        if current is not None:
            idx = self.mode_combo.findData((current.width, current.height))
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        self.primary_checkbox.setChecked(output.primary)
        self._refresh_rate_choices()

    def _refresh_rate_choices(self) -> None:
        if self.output is None:
            return
        res = self.mode_combo.currentData()
        self.rate_combo.clear()
        if res is None:
            return
        for mode in self.output.modes:
            if (mode.width, mode.height) == res:
                self.rate_combo.addItem(f"{mode.rate:g}Hz", mode.rate)
        current = self.output.current_mode()
        if current is not None and (current.width, current.height) == res:
            idx = self.rate_combo.findData(current.rate)
            if idx >= 0:
                self.rate_combo.setCurrentIndex(idx)

    def current_selection(self) -> dict:
        return {
            "mode": self.mode_combo.currentData(),
            "rate": self.rate_combo.currentData(),
            "primary": self.primary_checkbox.isChecked(),
            "scale": self.scale_spin.value() if self.blurry_scale_checkbox.isChecked() else 1.0,
        }
