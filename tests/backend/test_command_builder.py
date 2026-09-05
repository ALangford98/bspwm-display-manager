from bspwm_display_manager.backend.command_builder import build_scale_env, build_xrandr_args
from bspwm_display_manager.backend.models import Mode, Output


def _output(name, w, h, rate, x, y, primary=False, off=False, scale=(1.0, 1.0)):
    modes = [] if off else [Mode(width=w, height=h, rate=rate, id="0x1", current=True, preferred=True)]
    return Output(name=name, connected=not off, primary=primary, edid="e",
                  x=x, y=y, rotation="normal", scale_x=scale[0], scale_y=scale[1], modes=modes)


def test_builds_one_output_clause_per_output_in_order():
    outs = [
        _output("DP-1", 2560, 1440, 59.95, 0, 0),
        _output("eDP-1", 1920, 1200, 60.03, 1600, 1440, primary=True),
    ]
    args = build_xrandr_args(outs)
    assert args == [
        "--output", "DP-1", "--mode", "2560x1440", "--rate", "59.95",
        "--pos", "0x0", "--rotate", "normal",
        "--output", "eDP-1", "--mode", "1920x1200", "--rate", "60.03",
        "--pos", "1600x1440", "--rotate", "normal", "--primary",
    ]


def test_off_output_only_gets_output_and_off():
    outs = [_output("HDMI-1", 0, 0, 0, 0, 0, off=True)]
    args = build_xrandr_args(outs)
    assert args == ["--output", "HDMI-1", "--off"]


def test_non_default_scale_adds_scale_flag():
    outs = [_output("DP-2", 3840, 2160, 59.98, 0, 0, scale=(0.5, 0.5))]
    args = build_xrandr_args(outs)
    assert args == [
        "--output", "DP-2", "--mode", "3840x2160", "--rate", "59.98",
        "--pos", "0x0", "--rotate", "normal", "--scale", "0.5x0.5",
    ]


def test_build_scale_env_100_percent_is_baseline_dpi():
    env = build_scale_env(100)
    assert env["GDK_SCALE"] == "1"
    assert env["QT_SCALE_FACTOR"] == "1"
    assert env["QT_AUTO_SCREEN_SCALE_FACTOR"] == "0"
    assert env["Xft.dpi"] == "96"


def test_build_scale_env_150_percent():
    env = build_scale_env(150)
    assert env["GDK_SCALE"] == "1.5"
    assert env["QT_SCALE_FACTOR"] == "1.5"
    assert env["Xft.dpi"] == "144"
