from __future__ import annotations

import sys
import time
from pathlib import Path

from bspwm_display_manager.backend import apply, edid, profile_store, xrandr_client, xrandr_parser
from bspwm_display_manager.backend.profile import Profile
from bspwm_display_manager.daemon import notify


def find_matching_profile(fingerprint: str, profiles_dir: Path) -> Profile | None:
    for name in profile_store.list_profiles(profiles_dir):
        profile = profile_store.load(name, profiles_dir)
        if profile.fingerprint == fingerprint:
            return profile
    return None


def check_and_apply(last_fingerprint: str | None, profiles_dir: Path) -> str:
    state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
    current_fingerprint = edid.fingerprint(state.connected())
    if current_fingerprint == last_fingerprint:
        return current_fingerprint

    profile = find_matching_profile(current_fingerprint, profiles_dir)
    if profile is None:
        notify.send_notification(
            "bspwm-display-manager",
            "No saved profile matches the connected displays.",
        )
        return current_fingerprint

    outcome = apply.replay_profile(profile)
    if outcome.ok:
        notify.send_notification("bspwm-display-manager", f"Applied profile {profile.name!r}.")
    else:
        notify.send_notification(
            "bspwm-display-manager", f"Failed to apply {profile.name!r}: {outcome.message}"
        )
    return current_fingerprint


def run_forever(profiles_dir: Path, interval_seconds: float = 3.0) -> None:
    """Polls check_and_apply on a fixed interval, forever. A transient
    failure in one tick is logged (stdout/stderr, which a systemd user
    service routes to journalctl) and the loop continues -- a
    crash-looping service is worse than one that logs and retries."""
    last_fingerprint: str | None = None
    while True:
        try:
            last_fingerprint = check_and_apply(last_fingerprint, profiles_dir)
        except Exception as exc:
            print(f"bspwm-display-manager daemon: {exc}", file=sys.stderr)
        time.sleep(interval_seconds)
