from pathlib import Path
from unittest.mock import patch

from bspwm_display_manager.backend.profile import Profile
from bspwm_display_manager.daemon.watcher import find_matching_profile


def _profile(name, fingerprint):
    return Profile(
        name=name, fingerprint=fingerprint, scale_percent=100,
        outputs=[], desktop_assignment={}, hooks=[],
    )


def test_find_matching_profile_returns_the_profile_with_the_matching_fingerprint():
    work = _profile("work", "fp-office")
    home = _profile("home", "fp-laptop-only")
    with patch("bspwm_display_manager.daemon.watcher.profile_store.list_profiles",
               return_value=["home", "work"]), \
         patch("bspwm_display_manager.daemon.watcher.profile_store.load",
               side_effect=lambda name, d: {"home": home, "work": work}[name]):
        result = find_matching_profile("fp-office", Path("/fake/profiles"))
    assert result is work


def test_find_matching_profile_returns_none_when_nothing_matches():
    home = _profile("home", "fp-laptop-only")
    with patch("bspwm_display_manager.daemon.watcher.profile_store.list_profiles",
               return_value=["home"]), \
         patch("bspwm_display_manager.daemon.watcher.profile_store.load", return_value=home):
        result = find_matching_profile("fp-unknown-combo", Path("/fake/profiles"))
    assert result is None


def test_find_matching_profile_returns_none_for_an_empty_profiles_directory():
    with patch("bspwm_display_manager.daemon.watcher.profile_store.list_profiles", return_value=[]):
        result = find_matching_profile("anything", Path("/fake/profiles"))
    assert result is None
