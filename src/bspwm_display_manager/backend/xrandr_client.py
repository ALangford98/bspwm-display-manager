from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class ApplyResult:
    ok: bool
    returncode: int
    stderr: str


def query_verbose() -> str:
    result = subprocess.run(
        ["xrandr", "--verbose"], capture_output=True, text=True, check=False
    )
    return result.stdout


def apply(args: list[str]) -> ApplyResult:
    result = subprocess.run(
        ["xrandr", *args], capture_output=True, text=True, check=False
    )
    return ApplyResult(ok=result.returncode == 0, returncode=result.returncode, stderr=result.stderr)
