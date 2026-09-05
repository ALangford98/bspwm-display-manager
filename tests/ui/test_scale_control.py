from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.scale_control import SessionScaleControl


def _output(name, w, h):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_defaults_to_the_suggested_percent(qapp):
    control = SessionScaleControl()
    control.set_outputs([_output("DP-1", 2560, 1440), _output("DP-2", 3840, 2160)])
    assert control.value() == 150


def test_user_choice_overrides_the_suggestion(qapp):
    control = SessionScaleControl()
    control.set_outputs([_output("DP-1", 2560, 1440), _output("DP-2", 3840, 2160)])
    control.combo.setCurrentText("100%")
    assert control.value() == 100
