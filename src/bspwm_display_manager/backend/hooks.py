from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class HookResult:
    command: str
    ok: bool
    stderr: str


_TIMEOUT_SECONDS = 10


def run_hooks(commands: list[str]) -> list[HookResult]:
    results = []
    for command in commands:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, check=False,
                timeout=_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            # A hook that backgrounds a long-lived process (e.g. `setsid -f
            # some-daemon`) without redirecting its own stdout/stderr leaves
            # capture_output's pipe write end open in that grandchild for as
            # long as it keeps running -- this read would otherwise block
            # forever waiting for an EOF that never comes, freezing apply
            # (and, worse, the hotplug daemon) rather than just this hook.
            results.append(HookResult(
                command=command, ok=False,
                stderr=(
                    f"hook timed out after {_TIMEOUT_SECONDS}s -- a command that "
                    "backgrounds a long-lived process must redirect its own "
                    "output, e.g. 'cmd >/dev/null 2>&1 </dev/null', or this "
                    "never sees EOF"
                ),
            ))
            continue
        results.append(HookResult(command=command, ok=result.returncode == 0, stderr=result.stderr))
    return results
