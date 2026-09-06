from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from bspwm_display_manager.backend import apply, bspc_client, edid, profile_store
from bspwm_display_manager.backend import xrandr_client, xrandr_parser
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.backend.profile import OutputSpec, Profile
from bspwm_display_manager.ui.apply_dialog import ApplyConfirmDialog
from bspwm_display_manager.ui.canvas import DisplayCanvas
from bspwm_display_manager.ui.desktop_panel import DesktopAssignmentPanel
from bspwm_display_manager.ui.output_panel import OutputPanel
from bspwm_display_manager.ui.scale_control import SessionScaleControl

PROFILES_DIR = Path.home() / ".config" / "bspwm-display-manager" / "profiles"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("bspwm Display Manager")

        self.canvas = DisplayCanvas()
        self.output_select_combo = QComboBox()
        self.output_panel = OutputPanel()
        self.scale_control = SessionScaleControl()
        self.desktop_panel = DesktopAssignmentPanel()
        self.apply_button = QPushButton("Apply")
        self.save_button = QPushButton("Save Profile")
        self.load_combo = QComboBox()
        self.load_button = QPushButton("Load")

        self.output_select_combo.currentTextChanged.connect(self._on_output_selected)
        self.apply_button.clicked.connect(self._on_apply)
        self.save_button.clicked.connect(self._on_save)
        self.load_button.clicked.connect(self._on_load)

        side = QVBoxLayout()
        side.addWidget(self.output_select_combo)
        side.addWidget(self.output_panel)
        side.addWidget(self.scale_control)
        side.addWidget(self.desktop_panel)
        side.addWidget(self.apply_button)
        side.addWidget(self.save_button)
        load_row = QHBoxLayout()
        load_row.addWidget(self.load_combo)
        load_row.addWidget(self.load_button)
        side.addLayout(load_row)

        root = QHBoxLayout()
        root.addWidget(self.canvas, stretch=2)
        side_widget = QWidget()
        side_widget.setLayout(side)
        root.addWidget(side_widget, stretch=1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._last_good_outputs: list[Output] = []
        self._refresh_from_system()

    def _refresh_from_system(self) -> None:
        state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
        connected = state.connected()
        self._last_good_outputs = list(connected)

        self.canvas.set_outputs(connected)
        self.scale_control.set_outputs(connected)

        self.output_select_combo.blockSignals(True)
        self.output_select_combo.clear()
        self.output_select_combo.addItems([o.name for o in connected])
        self.output_select_combo.blockSignals(False)
        if connected:
            self.output_panel.set_output(connected[0])

        names = [o.name for o in connected]
        self.desktop_panel.set_monitors(names)
        self.desktop_panel.load_assignment(
            {name: bspc_client.query_desktop_names(monitor=name) for name in names}
        )

        self.load_combo.clear()
        self.load_combo.addItems(profile_store.list_profiles(PROFILES_DIR))

    def _on_output_selected(self, name: str) -> None:
        match = next((o for o in self._last_good_outputs if o.name == name), None)
        if match is not None:
            self.output_panel.set_output(match)

    def _collect_outputs_for_apply(self) -> list[Output]:
        """Builds the outputs to apply: each output's last-known geometry,
        with the canvas's dragged position and — for whichever output is
        currently loaded in output_panel — that panel's edited
        mode/rate/primary/scale merged in. output_panel edits only one
        output at a time; _on_output_selected keeps it in sync with
        output_select_combo.

        If the panel's edit makes the selected output primary, every
        OTHER output is forced non-primary here -- xrandr rejects (or
        behaves ambiguously on) a command with more than one --primary
        flag, and _last_good_outputs may still have a stale primary on a
        different output from before this edit."""
        positions = self.canvas.positions()
        selected = self.output_panel.output
        selection = self.output_panel.current_selection() if selected is not None else None
        new_primary_forces_others_off = selection is not None and selection["primary"]

        outputs = []
        for out in self._last_good_outputs:
            x, y = positions.get(out.name, (out.x, out.y))
            if selected is not None and out.name == selected.name and selection["mode"] is not None:
                width, height = selection["mode"]
                mode = Mode(width=width, height=height, rate=selection["rate"],
                            id="", current=True, preferred=False)
                outputs.append(Output(
                    name=out.name, connected=True, primary=selection["primary"], edid=out.edid,
                    x=x, y=y, rotation=out.rotation,
                    scale_x=selection["scale"], scale_y=selection["scale"], modes=[mode],
                ))
            else:
                primary = False if new_primary_forces_others_off else out.primary
                outputs.append(Output(
                    name=out.name, connected=True, primary=primary, edid=out.edid,
                    x=x, y=y, rotation=out.rotation, scale_x=out.scale_x, scale_y=out.scale_y,
                    modes=out.modes,
                ))
        return outputs

    def _on_apply(self) -> None:
        outputs = self._collect_outputs_for_apply()
        order = [o.name for o in outputs]
        if not order:
            return
        primary = next((o.name for o in outputs if o.primary), order[0])

        outcome = apply.apply_geometry(outputs, overflow_target=primary, survivors=order)
        if not outcome.ok:
            QMessageBox.critical(self, "Apply failed", outcome.message)
            return

        dialog = ApplyConfirmDialog(parent=self)
        dialog.start()
        if dialog.exec() == dialog.DialogCode.Accepted:
            resolved = {o.name: o.name for o in outputs}
            profile = Profile(
                name="__pending__", fingerprint="", scale_percent=self.scale_control.value(),
                outputs=[], desktop_assignment=self.desktop_panel.assignment(), hooks=[],
            )
            reconcile_outcome = apply.finish_reconciliation(profile, resolved, order)
            if not reconcile_outcome.ok:
                QMessageBox.critical(self, "Apply failed", reconcile_outcome.message)
            self._last_good_outputs = outputs
        else:
            prev = self._last_good_outputs
            prev_order = [o.name for o in prev]
            prev_primary = next((o.name for o in prev if o.primary), prev_order[0])
            revert_outcome = apply.apply_geometry(prev, overflow_target=prev_primary, survivors=prev_order)
            if not revert_outcome.ok:
                # The single worst state this dialog exists to prevent:
                # a failed revert with no explanation. Always tell the
                # user, since there's no further fallback to try.
                QMessageBox.critical(self, "Revert failed", revert_outcome.message)
        self._refresh_from_system()

    def _on_save(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if not ok or not name:
            return
        outputs = self._collect_outputs_for_apply()
        specs = []
        name_to_pattern = {}
        for out in outputs:
            mode = out.current_mode()
            if mode is None:
                continue
            pattern = out.edid or out.name
            name_to_pattern[out.name] = pattern
            specs.append(OutputSpec(
                edid_or_pattern=pattern, mode=(mode.width, mode.height),
                rate=mode.rate, x=out.x, y=out.y, rotation=out.rotation,
                scale_x=out.scale_x, scale_y=out.scale_y, primary=out.primary,
            ))
        desktop_assignment = {
            name_to_pattern[mon]: names
            for mon, names in self.desktop_panel.assignment().items()
            if mon in name_to_pattern
        }
        try:
            existing = profile_store.load(name, PROFILES_DIR)
            hooks_list = existing.hooks
        except FileNotFoundError:
            hooks_list = []
        profile = Profile(
            name=name, fingerprint=edid.fingerprint(outputs),
            scale_percent=self.scale_control.value(), outputs=specs,
            desktop_assignment=desktop_assignment, hooks=hooks_list,
        )
        try:
            profile_store.save(profile, PROFILES_DIR)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        # Deliberately NOT a full _refresh_from_system(): that would
        # re-query live xrandr/bspc state and snap the canvas back to
        # the current on-screen layout, discarding the arrangement the
        # user just saved (and about to Apply). Only the profile list
        # needs to reflect the new save.
        self.load_combo.clear()
        self.load_combo.addItems(profile_store.list_profiles(PROFILES_DIR))

    def _on_load(self) -> None:
        name = self.load_combo.currentText()
        if not name:
            return
        try:
            profile = profile_store.load(name, PROFILES_DIR)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        try:
            outcome = apply.replay_profile(profile)
        except ValueError as exc:
            QMessageBox.critical(self, "Apply failed", str(exc))
            return
        if not outcome.ok:
            QMessageBox.critical(self, "Apply failed", outcome.message)
        self._refresh_from_system()
