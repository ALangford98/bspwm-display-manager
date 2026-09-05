from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.canvas import DisplayCanvas


def _output(name, w, h, x, y):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=x, y=y, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_set_outputs_creates_one_item_per_output(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([
        _output("DP-1", 2560, 1440, 0, 0),
        _output("eDP-1", 1920, 1200, 2560, 0),
    ])
    assert len(canvas.scene().items()) == 2


def test_positions_round_trips_through_the_scale_factor(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 100, 200)])
    assert canvas.positions() == {"DP-1": (100, 200)}


def test_positions_round_trips_a_position_not_divisible_by_scale_down(qapp):
    """SCALE_DOWN is 10 -- a position like x=105 isn't a clean multiple
    of it. Regression test for a version that used integer floor
    division on the way in (out.x // SCALE_DOWN, discarding the
    remainder) and couldn't recover it on the way out; 105 silently
    became 100. Real monitor positions are not guaranteed to land on
    multiples of 10."""
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 105, 207)])
    assert canvas.positions() == {"DP-1": (105, 207)}


def test_set_outputs_clears_previous_items(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 0, 0)])
    canvas.set_outputs([_output("eDP-1", 1920, 1200, 0, 0)])
    assert len(canvas.scene().items()) == 1
