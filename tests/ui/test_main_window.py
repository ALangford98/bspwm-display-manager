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
