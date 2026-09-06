from __future__ import annotations

import subprocess
import sys


def send_notification(title: str, message: str) -> None:
    """Best-effort desktop notification. Never raises: a missing or
    failing notify-send must not take down the daemon over UI sugar."""
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except OSError as exc:
        print(f"bspwm-display-manager daemon: notify-send unavailable ({exc})", file=sys.stderr)
