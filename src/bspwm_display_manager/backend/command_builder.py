from __future__ import annotations

from bspwm_display_manager.backend.models import Output

_BASE_DPI = 96


def build_xrandr_args(outputs: list[Output]) -> list[str]:
    args: list[str] = []
    for out in outputs:
        args += ["--output", out.name]
        mode = out.current_mode()
        if mode is None:
            args += ["--off"]
            continue
        args += [
            "--mode", f"{mode.width}x{mode.height}",
            "--rate", f"{mode.rate}",
            "--pos", f"{out.x}x{out.y}",
            "--rotate", out.rotation,
        ]
        if out.primary:
            args += ["--primary"]
        if (out.scale_x, out.scale_y) != (1.0, 1.0):
            args += ["--scale", f"{out.scale_x}x{out.scale_y}"]
    return args


def build_scale_env(percent: int) -> dict[str, str]:
    factor = percent / 100
    return {
        "GDK_SCALE": _trim(factor),
        "QT_SCALE_FACTOR": _trim(factor),
        "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
        "Xft.dpi": str(int(_BASE_DPI * factor)),
    }


def _trim(value: float) -> str:
    return f"{value:g}"
