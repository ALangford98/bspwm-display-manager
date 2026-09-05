from pathlib import Path
from unittest.mock import patch

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "xrandr_verbose_single_laptop.txt").read_text()


def test_main_window_constructs_and_populates_from_system_state(qapp):
    from bspwm_display_manager.ui.main_window import MainWindow

    with patch("bspwm_display_manager.ui.main_window.xrandr_client.query_verbose", return_value=FIXTURE), \
         patch("bspwm_display_manager.ui.main_window.bspc_client.query_desktop_names", return_value=["term"]), \
         patch("bspwm_display_manager.ui.main_window.profile_store.list_profiles", return_value=["home"]):
        window = MainWindow()

    assert len(window.canvas.scene().items()) == 1
    assert window.load_combo.count() == 1
    assert window.desktop_panel.assignment() == {"eDP-1": ["term"]}


def test_collect_outputs_for_apply_forces_other_outputs_non_primary_when_selected_becomes_primary(qapp):
    """Regression test: xrandr rejects (or behaves ambiguously on) a
    command with more than one --primary flag. eDP-1 is primary in the
    dual_office fixture; selecting DP-1 in output_select_combo and
    checking its Primary box must clear eDP-1's primary flag in the
    outputs _collect_outputs_for_apply builds, not just add a second
    one."""
    from bspwm_display_manager.ui.main_window import MainWindow

    fixture = (Path(__file__).parent.parent / "fixtures" / "xrandr_verbose_dual_office.txt").read_text()
    with patch("bspwm_display_manager.ui.main_window.xrandr_client.query_verbose", return_value=fixture), \
         patch("bspwm_display_manager.ui.main_window.bspc_client.query_desktop_names", return_value=[]), \
         patch("bspwm_display_manager.ui.main_window.profile_store.list_profiles", return_value=[]):
        window = MainWindow()

    window.output_select_combo.setCurrentText("DP-1")
    assert window.output_panel.output.name == "DP-1"
    window.output_panel.primary_checkbox.setChecked(True)

    outputs = window._collect_outputs_for_apply()
    primaries = [o.name for o in outputs if o.primary]
    assert primaries == ["DP-1"]
