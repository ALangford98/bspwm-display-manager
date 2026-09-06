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


from bspwm_display_manager.backend.apply import ApplyOutcome
from bspwm_display_manager.backend.models import LayoutState, Mode, Output
from bspwm_display_manager.daemon.watcher import check_and_apply


def _state(fingerprint_source_name="eDP-1"):
    mode = Mode(width=1920, height=1200, rate=60.03, id="0x1", current=True, preferred=True)
    out = Output(name=fingerprint_source_name, connected=True, primary=True, edid="edid-laptop",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])
    return LayoutState(outputs=[out])


def test_check_and_apply_does_nothing_when_fingerprint_is_unchanged():
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="same-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile") as find, \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile") as replay:
        result = check_and_apply("same-fp", Path("/fake/profiles"))
    assert result == "same-fp"
    find.assert_not_called()
    replay.assert_not_called()


def test_check_and_apply_replays_the_matching_profile_on_a_change():
    matched = _profile("work", "new-fp")
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="new-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               return_value=ApplyOutcome(ok=True, message="")) as replay, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "new-fp"
    replay.assert_called_once_with(matched)
    notify.assert_called_once()
    assert "work" in notify.call_args.args[1]


def test_check_and_apply_notifies_failure_without_raising():
    matched = _profile("work", "new-fp")
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="new-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               return_value=ApplyOutcome(ok=False, message="xrandr: bad mode")), \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "new-fp"
    assert "bad mode" in notify.call_args.args[1]


def test_check_and_apply_notifies_when_no_profile_matches():
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="unknown-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=None), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile") as replay, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "unknown-fp"
    replay.assert_not_called()
    notify.assert_called_once()


def test_check_and_apply_treats_startup_none_as_a_change():
    """last_fingerprint is None on the daemon's very first tick -- this
    must be treated as a change (so the right profile gets applied at
    login), not compared literally against the current fingerprint
    string."""
    matched = _profile("home", "laptop-fp")
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="laptop-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               return_value=ApplyOutcome(ok=True, message="")) as replay, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification"):
        result = check_and_apply(None, Path("/fake/profiles"))
    assert result == "laptop-fp"
    replay.assert_called_once_with(matched)
