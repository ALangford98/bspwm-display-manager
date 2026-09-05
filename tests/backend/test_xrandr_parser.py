from pathlib import Path

from bspwm_display_manager.backend.xrandr_parser import parse_verbose

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parses_single_connected_laptop_output():
    text = (FIXTURES / "xrandr_verbose_single_laptop.txt").read_text()
    state = parse_verbose(text)
    connected = state.connected()
    assert [o.name for o in connected] == ["eDP-1"]

    edp = connected[0]
    assert edp.primary is True
    assert edp.x == 0 and edp.y == 0
    assert edp.edid is not None and edp.edid.startswith("00ffffffffffff")
    cur = edp.current_mode()
    assert (cur.width, cur.height, cur.rate) == (1920, 1200, 60.03)
    assert cur.preferred is True


def test_disconnected_outputs_are_present_but_not_connected():
    text = (FIXTURES / "xrandr_verbose_single_laptop.txt").read_text()
    state = parse_verbose(text)
    names = {o.name: o.connected for o in state.outputs}
    assert names == {"eDP-1": True, "HDMI-1": False, "DP-1": False}


def test_parses_three_connected_outputs_with_positions():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    by_name = {o.name: o for o in state.connected()}
    assert set(by_name) == {"eDP-1", "DP-1", "DP-2"}
    assert (by_name["DP-1"].x, by_name["DP-1"].y) == (0, 0)
    assert (by_name["DP-2"].x, by_name["DP-2"].y) == (2560, 0)
    assert (by_name["eDP-1"].x, by_name["eDP-1"].y) == (1600, 1440)
    assert by_name["eDP-1"].primary is True
    assert by_name["DP-1"].primary is False


def test_preferred_mode_can_differ_from_current_mode():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    dp2 = next(o for o in state.connected() if o.name == "DP-2")
    assert (dp2.current_mode().width, dp2.current_mode().height) == (2560, 1440)
    assert (dp2.preferred_mode().width, dp2.preferred_mode().height) == (3840, 2160)


def test_edid_differs_per_output():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    by_name = {o.name: o.edid for o in state.connected()}
    assert len({by_name["eDP-1"], by_name["DP-1"], by_name["DP-2"]}) == 3
