from __future__ import annotations

from bspwm_display_manager.backend import bspc_client

_PLACEHOLDER = "__bsp_retiring__"


class ReconciliationError(RuntimeError):
    """A bspc call failed. Retirement and assignment are both idempotent
    by construction, so the caller can safely retry the whole operation
    rather than trying to resume mid-way."""


def retire_monitors(overflow_target: str, survivors: list[str]) -> None:
    """Move every desktop off any monitor not in `survivors`, then
    remove that monitor. MUST be called before the xrandr command that
    disables/reconfigures the losing output — bspc_client.remove_monitor
    drops (does not merge) a monitor's windows the instant it runs."""
    keep = set(survivors) | {overflow_target}
    for mon in bspc_client.query_monitor_names():
        if mon in keep:
            continue
        # A monitor can never have zero desktops, so bspc refuses to move
        # its last one — add a disposable placeholder first so no real
        # desktop is ever "the last one" while being moved off.
        if not bspc_client.add_desktop(mon, _PLACEHOLDER):
            raise ReconciliationError(f"failed to add placeholder desktop on {mon!r}")
        for desk in bspc_client.query_desktop_names(monitor=mon):
            if desk == _PLACEHOLDER:
                continue
            if not bspc_client.move_desktop_to_monitor(desk, overflow_target):
                raise ReconciliationError(f"failed to move desktop {desk!r} off {mon!r}")
        if not bspc_client.remove_monitor(mon):
            raise ReconciliationError(f"failed to remove monitor {mon!r}")


def assign_desktops(target: str, names: list[str]) -> None:
    """Move each named desktop to `target` by identity if it exists
    anywhere, else create it fresh. Never uses `bspc monitor -d`, which
    silently folds a shrinking desktop list's dropped names into the
    last name in the new list instead of releasing them elsewhere.

    Skips the move entirely for a desktop already on `target`: bspc
    silently refuses to move a monitor's LAST desktop (a documented
    behavior, see this module's docstring and the design spec's Prior
    Art section) -- re-applying an already-correct profile where that
    desktop is the target monitor's only one would otherwise abort
    reconciliation on a call that should have been a no-op."""
    already_there = set(bspc_client.query_desktop_names(monitor=target))
    for name in names:
        if name in already_there:
            continue
        if bspc_client.desktop_exists(name):
            if not bspc_client.move_desktop_to_monitor(name, target):
                raise ReconciliationError(f"failed to move desktop {name!r} to {target!r}")
        else:
            if not bspc_client.add_desktop(target, name):
                raise ReconciliationError(f"failed to add desktop {name!r} on {target!r}")


def sweep_placeholder_desktops(expected_names: set[str]) -> None:
    """Remove any desktop not in `expected_names` (e.g. bspwm's
    auto-created blank desktop on a newly-appeared monitor), but only if
    it holds no windows, so nothing unexpected is silently destroyed."""
    for name in bspc_client.query_desktop_names():
        if name in expected_names:
            continue
        if bspc_client.desktop_is_empty(name):
            if not bspc_client.remove_desktop(name):
                raise ReconciliationError(f"failed to remove stray desktop {name!r}")


def reset_active_padding(active_monitors: list[str]) -> None:
    for mon in active_monitors:
        if not bspc_client.reset_padding(mon):
            raise ReconciliationError(f"failed to reset padding on {mon!r}")


def reconcile(
    active_monitors: list[str],
    desktop_assignment: dict[str, list[str]],
    order: list[str],
) -> None:
    """Everything that happens after a successful xrandr apply. Does NOT
    call retire_monitors — that must run before the xrandr apply, so the
    caller (backend.apply) is responsible for sequencing it separately."""
    reset_active_padding(active_monitors)
    for target, names in desktop_assignment.items():
        assign_desktops(target, names)
    if not bspc_client.reorder_monitors(order):
        raise ReconciliationError(f"failed to reorder monitors: {order!r}")
    expected = {name for names in desktop_assignment.values() for name in names}
    sweep_placeholder_desktops(expected)
