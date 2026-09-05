from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.output_panel import OutputPanel


def _output():
    modes = [
        Mode(width=2560, height=1440, rate=59.95, id="0x1", current=True, preferred=True),
        Mode(width=1920, height=1080, rate=60.0, id="0x2", current=False, preferred=False),
    ]
    return Output(name="DP-1", connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=modes)


def test_set_output_populates_mode_choices(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    assert panel.mode_combo.count() == 2


def test_current_selection_defaults_to_the_outputs_current_mode(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    sel = panel.current_selection()
    assert sel["mode"] == (2560, 1440)
    assert sel["rate"] == 59.95
    assert sel["primary"] is False


def test_blurry_scale_hidden_until_opted_in(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    assert panel.scale_spin.isVisibleTo(panel) is False
    panel.blurry_scale_checkbox.setChecked(True)
    assert panel.scale_spin.isVisibleTo(panel) is True
