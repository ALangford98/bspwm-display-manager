from __future__ import annotations

import subprocess

_PADDING_EDGES = ("top_padding", "bottom_padding", "left_padding", "right_padding")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bspc", *args], capture_output=True, text=True, check=False)


def query_monitor_names() -> list[str]:
    result = _run(["query", "-M", "--names"])
    return [l for l in result.stdout.splitlines() if l]


def query_desktop_names(monitor: str | None = None) -> list[str]:
    args = ["query", "-D"]
    if monitor is not None:
        args += ["-m", monitor]
    args += ["--names"]
    result = _run(args)
    return [l for l in result.stdout.splitlines() if l]


def desktop_exists(name: str) -> bool:
    return _run(["query", "-D", "-d", name]).returncode == 0


def move_desktop_to_monitor(desktop: str, target: str) -> None:
    _run(["desktop", desktop, "--to-monitor", target])


def add_desktop(monitor: str, name: str) -> None:
    _run(["monitor", monitor, "-a", name])


def remove_desktop(name: str) -> None:
    _run(["desktop", name, "-r"])


def remove_monitor(name: str) -> None:
    _run(["monitor", name, "-r"])


def reset_padding(monitor: str) -> None:
    for edge in _PADDING_EDGES:
        _run(["config", "-m", monitor, edge, "0"])


def reorder_monitors(order: list[str]) -> None:
    _run(["wm", "-O", *order])
