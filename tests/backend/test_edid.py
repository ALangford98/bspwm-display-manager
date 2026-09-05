from bspwm_display_manager.backend.edid import fingerprint
from bspwm_display_manager.backend.models import Output


def _o(name, edid):
    return Output(name=name, connected=True, primary=False, edid=edid,
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])


def test_fingerprint_is_stable_regardless_of_input_order():
    a = [_o("DP-1", "aaa"), _o("DP-2", "bbb")]
    b = [_o("DP-2", "bbb"), _o("DP-1", "aaa")]
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_is_stable_regardless_of_port_name():
    a = [_o("DP-1", "aaa"), _o("DP-2", "bbb")]
    b = [_o("HDMI-1", "aaa"), _o("DP-9", "bbb")]
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_differs_for_different_monitor_sets():
    a = [_o("DP-1", "aaa")]
    b = [_o("DP-1", "ccc")]
    assert fingerprint(a) != fingerprint(b)


def test_fingerprint_ignores_outputs_with_no_edid():
    a = [_o("DP-1", "aaa"), _o("VIRTUAL-1", None)]
    b = [_o("DP-1", "aaa")]
    assert fingerprint(a) == fingerprint(b)
