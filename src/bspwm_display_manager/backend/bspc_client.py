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


def desktop_is_empty(name: str) -> bool:
    result = _run(["query", "-N", "-d", name, "-n", ".window"])
    return result.stdout.strip() == ""


def move_desktop_to_monitor(desktop: str, target: str) -> bool:
    return _run(["desktop", desktop, "--to-monitor", target]).returncode == 0


def add_desktop(monitor: str, name: str) -> bool:
    return _run(["monitor", monitor, "-a", name]).returncode == 0


def remove_desktop(name: str) -> bool:
    return _run(["desktop", name, "-r"]).returncode == 0


def remove_monitor(name: str) -> bool:
    return _run(["monitor", name, "-r"]).returncode == 0


def reset_padding(monitor: str) -> bool:
    ok = True
    for edge in _PADDING_EDGES:
        if _run(["config", "-m", monitor, edge, "0"]).returncode != 0:
            ok = False
    return ok


def reorder_monitors(order: list[str]) -> bool:
    return _run(["wm", "-O", *order]).returncode == 0
