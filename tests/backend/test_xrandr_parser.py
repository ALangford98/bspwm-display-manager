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


def test_negative_offset_is_parsed_not_dropped_to_zero():
    """A monitor positioned below/left of the origin uses a '-' instead of
    the second '+' in its geometry (e.g. 1920x1080+0-1080). Regression
    test: an earlier version of this regex hard-coded '+' for both
    signs, silently defaulting negative offsets to 0."""
    text = (
        "HDMI-1 connected 1920x1080+0-1080 (0x4a) normal "
        "(normal left inverted right x axis y axis) 520mm x 320mm\n"
        "  1920x1080 (0x4a) 100.00MHz -HSync +VSync *current +preferred\n"
        "        v: height 1080 start 1081 end 1084 total 1118           clock  60.00Hz\n"
    )
    state = parse_verbose(text)
    assert (state.outputs[0].x, state.outputs[0].y) == (0, -1080)


def test_unrecognized_connection_status_does_not_corrupt_the_prior_output():
    """xrandr can report a line like 'DP-5 unknown connection (...)' for
    some outputs. Regression test: an earlier version silently kept
    `current` pointed at the previous output when a header line's status
    didn't match connected|disconnected exactly, so DP-5's property lines
    got misattributed to eDP-1 instead of being cleanly skipped."""
    text = (
        "eDP-1 connected primary 1920x1200+0+0 (0x49) normal "
        "(normal left inverted right x axis y axis) 301mm x 188mm\n"
        "  1920x1200 (0x49) 100.00MHz -HSync -VSync *current +preferred\n"
        "        v: height 1200 start 1203 end 1217 total 1236           clock  60.00Hz\n"
        "DP-5 unknown connection (normal left inverted right x axis y axis)\n"
        "\tCONNECTOR_ID: 999\n"
    )
    state = parse_verbose(text)
    assert [o.name for o in state.outputs] == ["eDP-1", "DP-5"]
    edp1 = state.outputs[0]
    assert len(edp1.modes) == 1
    dp5 = state.outputs[1]
    assert dp5.connected is False


def test_rotation_is_captured_from_the_header_line():
    text = (
        "DP-2 connected 1080x1920+0+0 (0x4b) left "
        "(normal left inverted right x axis y axis) 300mm x 500mm\n"
    )
    state = parse_verbose(text)
    assert state.outputs[0].rotation == "left"
