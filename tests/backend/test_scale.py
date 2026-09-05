from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.backend.scale import suggest_global_scale


def _o(name, w, h):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_suggests_150_percent_for_clean_1point5x_pair():
    outs = [_o("DP-1", 2560, 1440), _o("DP-2", 3840, 2160)]
    assert suggest_global_scale(outs) == 150


def test_suggests_100_percent_for_matching_resolutions():
    outs = [_o("DP-1", 1920, 1080), _o("DP-2", 1920, 1080)]
    assert suggest_global_scale(outs) == 100


def test_suggests_100_percent_for_a_single_output():
    outs = [_o("eDP-1", 1920, 1200)]
    assert suggest_global_scale(outs) == 100


def test_falls_back_to_100_for_a_non_clean_ratio():
    outs = [_o("DP-1", 1920, 1080), _o("DP-2", 2560, 1440)]
    assert suggest_global_scale(outs) == 100
