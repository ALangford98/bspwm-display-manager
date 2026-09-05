from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class HookResult:
    command: str
    ok: bool
    stderr: str


def run_hooks(commands: list[str]) -> list[HookResult]:
    results = []
    for command in commands:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        results.append(HookResult(command=command, ok=result.returncode == 0, stderr=result.stderr))
    return results
