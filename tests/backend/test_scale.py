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


def test_three_outputs_where_every_height_fits_one_of_two_clean_tiers():
    """Two matching 1440p monitors plus one 4K: every height is either
    at the 1x tier (1440) or the 1.5x tier (2160), so a single global
    scale keeps every screen consistently sized."""
    outs = [_o("DP-1", 2560, 1440), _o("DP-2", 2560, 1440), _o("DP-3", 3840, 2160)]
    assert suggest_global_scale(outs) == 150


def test_three_outputs_with_a_height_that_fits_neither_tier_falls_back_to_100():
    """Regression test: an earlier version of this function only ever
    checked the tallest/shortest pair, so three outputs at heights
    1000/1300/1500 wrongly returned 150 (matching the 1000:1500 = 1.5
    extremes) while silently ignoring that 1300 fits neither the 1x nor
    the 1.5x tier -- that output would not actually be consistently
    sized under the suggested scale."""
    outs = [_o("DP-1", 1000, 1000), _o("DP-2", 1300, 1300), _o("DP-3", 1500, 1500)]
    assert suggest_global_scale(outs) == 100
