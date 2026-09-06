from __future__ import annotations

import sys
import time
from pathlib import Path

from bspwm_display_manager.backend import apply, edid, profile_store, xrandr_client, xrandr_parser
from bspwm_display_manager.backend.profile import Profile
from bspwm_display_manager.daemon import notify

_DEBOUNCE_SECONDS = 1.0


def find_matching_profile(fingerprint: str, profiles_dir: Path) -> Profile | None:
    for name in profile_store.list_profiles(profiles_dir):
        try:
            profile = profile_store.load(name, profiles_dir)
        except (OSError, ValueError, KeyError) as exc:
            print(
                f"bspwm-display-manager daemon: skipping unreadable profile {name!r} ({exc})",
                file=sys.stderr,
            )
            continue
        if profile.fingerprint == fingerprint:
            return profile
    return None


def _observe() -> str | None:
    """Query current xrandr state and return its fingerprint, or None if
    no outputs are reported connected. xrandr silently returns empty
    stdout on failure (e.g. no DISPLAY, as under a systemd user service
    that hasn't imported the X session's environment) -- that parses to
    zero connected outputs, indistinguishable from a real
    all-monitors-unplugged state. Either way there is nothing to
    fingerprint or match a profile against."""
    state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
    connected = state.connected()
    if not connected:
        return None
    return edid.fingerprint(connected)


def check_and_apply(last_fingerprint: str | None, profiles_dir: Path) -> str:
    current_fingerprint = _observe()
    if current_fingerprint is None:
        print(
            "bspwm-display-manager daemon: no connected outputs reported "
            "(is DISPLAY set? did xrandr fail?) -- skipping this tick",
            file=sys.stderr,
        )
        # Do NOT cache this as a real observation -- doing so would
        # permanently wedge the daemon (every later tick would see "no
        # change" against this same sentinel) the moment xrandr fails
        # even once.
        return last_fingerprint or ""
    if current_fingerprint == last_fingerprint:
        return current_fingerprint

    # Debounce: a physical hotplug (especially a dock or a DP-MST daisy
    # chain) can report several different intermediate connected-sets in
    # quick succession before settling -- this project's own prior-art
    # scripts document exactly this kind of link-training flakiness.
    # Confirm the new state is still there after a short pause before
    # acting on it, rather than risking a full apply (retire + xrandr +
    # reconcile + hooks) against a transient mid-enumeration set.
    time.sleep(_DEBOUNCE_SECONDS)
    confirmed_fingerprint = _observe()
    if confirmed_fingerprint != current_fingerprint:
        # Still settling -- don't act now. Report the ORIGINAL
        # last_fingerprint unchanged so the next regular poll tick
        # re-evaluates from scratch once things stabilize.
        return last_fingerprint or ""
    current_fingerprint = confirmed_fingerprint

    profile = find_matching_profile(current_fingerprint, profiles_dir)
    if profile is None:
        notify.send_notification(
            "bspwm-display-manager",
            "No saved profile matches the connected displays.",
        )
        return current_fingerprint

    try:
        outcome = apply.replay_profile(profile)
    except ValueError as exc:
        # resolve_targets (inside replay_profile) can raise this even on
        # a fingerprint match -- an OutputSpec's edid_or_pattern can be a
        # name/glob fallback rather than a real EDID. Notify once and
        # move on, exactly like the CLI's own `except ValueError` around
        # this same call -- must not propagate to run_forever's blanket
        # handler, which would retry the same failing apply every poll
        # interval forever.
        notify.send_notification("bspwm-display-manager", f"Failed to apply {profile.name!r}: {exc}")
        return current_fingerprint

    if outcome.ok:
        print(f"bspwm-display-manager daemon: applied profile {profile.name!r}", file=sys.stderr)
        notify.send_notification("bspwm-display-manager", f"Applied profile {profile.name!r}.")
    else:
        print(
            f"bspwm-display-manager daemon: failed to apply {profile.name!r}: {outcome.message}",
            file=sys.stderr,
        )
        notify.send_notification(
            "bspwm-display-manager", f"Failed to apply {profile.name!r}: {outcome.message}"
        )
    return current_fingerprint


def run_forever(profiles_dir: Path, interval_seconds: float = 3.0) -> None:
    """Polls check_and_apply on a fixed interval, forever. A transient
    failure in one tick is logged (stderr, which a systemd user service
    routes to journalctl) and the loop continues -- a crash-looping
    service is worse than one that logs and retries."""
    last_fingerprint: str | None = None
    while True:
        try:
            last_fingerprint = check_and_apply(last_fingerprint, profiles_dir)
        except Exception as exc:
            print(f"bspwm-display-manager daemon: {exc}", file=sys.stderr)
        time.sleep(interval_seconds)
