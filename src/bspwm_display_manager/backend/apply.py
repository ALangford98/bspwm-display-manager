from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path

from bspwm_display_manager.backend import command_builder, hooks, reconcile
from bspwm_display_manager.backend import xrandr_client, xrandr_parser
from bspwm_display_manager.backend.models import LayoutState, Mode, Output
from bspwm_display_manager.backend.profile import Profile


@dataclass
class ApplyOutcome:
    ok: bool
    message: str


def resolve_targets(profile: Profile, state: LayoutState) -> dict[str, str]:
    """Map each OutputSpec.edid_or_pattern to the real connected output
    name it matches. Exact EDID match is tried across ALL connected
    outputs before falling back to fnmatch glob matching against output
    names -- as two separate passes, not interleaved -- so a real EDID
    string that happens to also look like a glob pattern can't be
    misidentified as a name-pattern match against some other, unrelated
    output that merely comes earlier in the connected list."""
    connected = state.connected()
    resolved: dict[str, str] = {}
    for spec in profile.outputs:
        pattern = spec.edid_or_pattern
        match = next((out.name for out in connected if out.edid == pattern), None)
        if match is None:
            match = next((out.name for out in connected if fnmatch.fnmatch(out.name, pattern)), None)
        if match is None:
            raise ValueError(f"no connected output matches {pattern!r}")
        resolved[pattern] = match
    return resolved


def _outputs_for_apply(profile: Profile, resolved: dict[str, str]) -> list[Output]:
    outputs = []
    for spec in profile.outputs:
        mode = Mode(width=spec.mode[0], height=spec.mode[1], rate=spec.rate,
                     id="", current=True, preferred=False)
        outputs.append(Output(
            name=resolved[spec.edid_or_pattern], connected=True, primary=spec.primary,
            edid=None, x=spec.x, y=spec.y, rotation=spec.rotation,
            scale_x=spec.scale_x, scale_y=spec.scale_y, modes=[mode],
        ))
    return outputs


def apply_geometry(outputs: list[Output], overflow_target: str, survivors: list[str]) -> ApplyOutcome:
    """Pre-confirm step: retire monitors that are dropping out, then run
    the xrandr apply. retire_monitors MUST run first -- see Task 9's
    reconcile.retire_monitors docstring for why calling it after xrandr
    reconfigures/disables the losing output is unsafe."""
    try:
        reconcile.retire_monitors(overflow_target=overflow_target, survivors=survivors)
    except reconcile.ReconciliationError as exc:
        return ApplyOutcome(ok=False, message=str(exc))
    args = command_builder.build_xrandr_args(outputs)
    try:
        result = xrandr_client.apply(args)
    except OSError as exc:
        # e.g. the xrandr binary itself is missing -- ApplyOutcome is the
        # whole contract Task 18's GUI gates on, so this must not escape
        # as a raw exception any more than ReconciliationError may.
        return ApplyOutcome(ok=False, message=str(exc))
    return ApplyOutcome(ok=result.ok, message=result.stderr)


def apply_scale_env(percent: int) -> None:
    env = command_builder.build_scale_env(percent)
    subprocess.run(["xrdb", "-merge"], input=f"Xft.dpi: {env['Xft.dpi']}\n",
                    text=True, check=False)
    env_path = Path.home() / ".config" / "bspwm-display-manager" / "env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"export {k}={v}\n" for k, v in env.items() if k != "Xft.dpi"]
    env_path.write_text("".join(lines))


def finish_reconciliation(profile: Profile, resolved: dict[str, str], order: list[str]) -> ApplyOutcome:
    """Post-confirm step: scale env, desktop reconciliation, then hooks.
    Catches Task 9's reconcile.ReconciliationError from reconcile.reconcile
    and reports it through ApplyOutcome instead of raising, so the
    CLI/GUI layers never need to know that exception type exists."""
    try:
        apply_scale_env(profile.scale_percent)
    except OSError as exc:
        # apply_scale_env writes a real file and shells out to xrdb --
        # both can raise (permission denied, xrdb missing). Same
        # never-raise contract as the ReconciliationError handling below.
        return ApplyOutcome(ok=False, message=str(exc))
    try:
        desktop_assignment = {
            resolved[pattern]: names for pattern, names in profile.desktop_assignment.items()
        }
    except KeyError as exc:
        return ApplyOutcome(ok=False, message=f"desktop_assignment references unknown output {exc}")
    try:
        reconcile.reconcile(active_monitors=order, desktop_assignment=desktop_assignment, order=order)
    except reconcile.ReconciliationError as exc:
        return ApplyOutcome(ok=False, message=str(exc))
    hooks.run_hooks(profile.hooks)
    return ApplyOutcome(ok=True, message="")


def replay_profile(profile: Profile) -> ApplyOutcome:
    """Full non-interactive CLI/daemon path: resolve -> apply_geometry ->
    finish_reconciliation. Returns whichever ApplyOutcome reflects the
    actual failure point; skips finish_reconciliation entirely if
    apply_geometry already failed."""
    state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
    resolved = resolve_targets(profile, state)
    order = [resolved[spec.edid_or_pattern] for spec in profile.outputs]
    overflow_target = next(
        (resolved[spec.edid_or_pattern] for spec in profile.outputs if spec.primary), None
    )
    if overflow_target is None:
        return ApplyOutcome(ok=False, message="profile has no primary output")
    outputs = _outputs_for_apply(profile, resolved)
    # Any connected output NOT named by this profile must be explicitly
    # turned off -- otherwise it stays live in X even though its bspwm
    # monitor was just retired by apply_geometry below.
    named = set(resolved.values())
    for out in state.connected():
        if out.name not in named:
            outputs.append(Output(
                name=out.name, connected=True, primary=False, edid=None,
                x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[],
            ))
    outcome = apply_geometry(outputs, overflow_target=overflow_target, survivors=order)
    if not outcome.ok:
        return outcome
    return finish_reconciliation(profile, resolved, order)
