from __future__ import annotations

from pathlib import Path

from bspwm_display_manager.backend import profile_store
from bspwm_display_manager.backend.profile import Profile


def find_matching_profile(fingerprint: str, profiles_dir: Path) -> Profile | None:
    for name in profile_store.list_profiles(profiles_dir):
        profile = profile_store.load(name, profiles_dir)
        if profile.fingerprint == fingerprint:
            return profile
    return None
