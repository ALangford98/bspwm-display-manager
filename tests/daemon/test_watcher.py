from pathlib import Path
from unittest.mock import patch

from bspwm_display_manager.backend import edid
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


def test_find_matching_profile_skips_a_profile_that_fails_to_load(capsys):
    """A hand-edited or corrupted profile JSON must not permanently
    disable matching for every OTHER profile -- profile_store.load can
    raise OSError/ValueError/KeyError for a malformed file; skip it and
    keep looking."""
    good = _profile("work", "fp-office")

    def fake_load(name, profiles_dir):
        if name == "broken":
            raise ValueError("bad json")
        return good

    with patch("bspwm_display_manager.daemon.watcher.profile_store.list_profiles",
               return_value=["broken", "work"]), \
         patch("bspwm_display_manager.daemon.watcher.profile_store.load", side_effect=fake_load):
        result = find_matching_profile("fp-office", Path("/fake/profiles"))
    assert result is good
    assert "broken" in capsys.readouterr().err


from bspwm_display_manager.backend.apply import ApplyOutcome
from bspwm_display_manager.backend.models import LayoutState, Mode, Output
from bspwm_display_manager.daemon.watcher import check_and_apply


def _state(fingerprint_source_name="eDP-1"):
    mode = Mode(width=1920, height=1200, rate=60.03, id="0x1", current=True, preferred=True)
    out = Output(name=fingerprint_source_name, connected=True, primary=True, edid="edid-laptop",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])
    return LayoutState(outputs=[out])


def test_fingerprint_is_stable_regardless_of_whether_an_output_is_currently_on_or_off():
    """check_and_apply's whole no-oscillation guarantee depends on this:
    an output that is physically connected but currently has no active
    mode (off) must fingerprint identically to the same output on --
    EDID doesn't change just because xrandr currently has no CRTC
    assigned to it. Locks in an invariant the daemon silently depends
    on (backend.edid.fingerprint and backend.models.LayoutState.connected
    are unchanged by this plan; this test only verifies the assumption)."""
    on_mode = Mode(width=1920, height=1200, rate=60.03, id="0x1", current=True, preferred=True)
    on_output = Output(name="eDP-1", connected=True, primary=True, edid="edid-laptop",
                        x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[on_mode])
    off_output = Output(name="eDP-1", connected=True, primary=True, edid="edid-laptop",
                         x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    assert edid.fingerprint([on_output]) == edid.fingerprint([off_output])


def test_check_and_apply_does_nothing_when_fingerprint_is_unchanged():
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="same-fp"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile") as find, \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile") as replay, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify_fn:
        result = check_and_apply("same-fp", Path("/fake/profiles"))
    assert result == "same-fp"
    find.assert_not_called()
    replay.assert_not_called()
    notify_fn.assert_not_called()


def test_check_and_apply_treats_no_connected_outputs_as_a_skip_not_a_real_observation(capsys):
    """xrandr silently returns empty stdout on failure (e.g. no DISPLAY,
    as under a systemd user service that hasn't imported the X session's
    environment) -- that parses to zero connected outputs,
    indistinguishable from a real all-monitors-unplugged state. Either
    way there is nothing to fingerprint or match against. Must not cache
    this as if it were a real observation: doing so would permanently
    wedge the daemon (every later tick would see "no change" against
    this same sentinel) the moment xrandr fails even once."""
    empty_state = LayoutState(outputs=[])
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=empty_state), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile") as find, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify_fn:
        result = check_and_apply("previous-fp", Path("/fake/profiles"))
    assert result == "previous-fp"
    find.assert_not_called()
    notify_fn.assert_not_called()
    assert "no connected outputs" in capsys.readouterr().err


def test_check_and_apply_empty_state_with_no_prior_fingerprint_returns_empty_string():
    """Must still satisfy the `-> str` return contract (never None) even
    on the very first tick if xrandr fails before ever succeeding once."""
    empty_state = LayoutState(outputs=[])
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=empty_state):
        result = check_and_apply(None, Path("/fake/profiles"))
    assert result == ""


def test_check_and_apply_does_not_act_on_an_unstable_intermediate_state():
    """A dock or DP-MST chain can report a different connected-set on
    two queries a moment apart while still enumerating. If the debounce
    re-check disagrees with the first reading, this tick must not act
    (no match lookup, no notify) and must not adopt the unstable reading
    as the new last_fingerprint -- the next regular poll tick
    re-evaluates from scratch."""
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", side_effect=["fp-a", "fp-b"]), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep") as sleep_fn, \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile") as find, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify_fn:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "old-fp"
    find.assert_not_called()
    notify_fn.assert_not_called()
    sleep_fn.assert_called_once()


def test_check_and_apply_replays_the_matching_profile_on_a_change():
    matched = _profile("work", "new-fp")
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="new-fp"), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep"), \
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
         patch("bspwm_display_manager.daemon.watcher.time.sleep"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               return_value=ApplyOutcome(ok=False, message="xrandr: bad mode")), \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "new-fp"
    assert "bad mode" in notify.call_args.args[1]


def test_check_and_apply_notifies_and_continues_when_replay_profile_raises_value_error():
    """resolve_targets (inside replay_profile) can raise ValueError even
    on a fingerprint match -- an OutputSpec's edid_or_pattern can be a
    name/glob fallback rather than a real EDID, which can stop resolving
    if a port name changes across a dock/cable swap. Must notify once
    and return the new fingerprint, exactly like the CLI's own `except
    ValueError` around this same call -- not propagate to run_forever's
    blanket handler, which would silently retry the same failing apply
    every poll interval forever."""
    matched = _profile("work", "new-fp")
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="new-fp"), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               side_effect=ValueError("no connected output matches 'edid-dell'")), \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification") as notify:
        result = check_and_apply("old-fp", Path("/fake/profiles"))
    assert result == "new-fp"
    notify.assert_called_once()
    assert "no connected output matches" in notify.call_args.args[1]


def test_check_and_apply_notifies_when_no_profile_matches():
    with patch("bspwm_display_manager.daemon.watcher.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.daemon.watcher.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.daemon.watcher.edid.fingerprint", return_value="unknown-fp"), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep"), \
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
         patch("bspwm_display_manager.daemon.watcher.time.sleep"), \
         patch("bspwm_display_manager.daemon.watcher.find_matching_profile", return_value=matched), \
         patch("bspwm_display_manager.daemon.watcher.apply.replay_profile",
               return_value=ApplyOutcome(ok=True, message="")) as replay, \
         patch("bspwm_display_manager.daemon.watcher.notify.send_notification"):
        result = check_and_apply(None, Path("/fake/profiles"))
    assert result == "laptop-fp"
    replay.assert_called_once_with(matched)


import pytest

from bspwm_display_manager.daemon.watcher import run_forever


class _StopLoop(Exception):
    """Sentinel used only to break run_forever's `while True` in tests."""


def test_run_forever_calls_check_and_apply_each_tick_and_sleeps_between():
    calls = []

    def fake_check(last, profiles_dir):
        calls.append(last)
        return f"fp-{len(calls)}"

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise _StopLoop()

    with patch("bspwm_display_manager.daemon.watcher.check_and_apply", side_effect=fake_check), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep", side_effect=fake_sleep):
        with pytest.raises(_StopLoop):
            run_forever(Path("/fake/profiles"), interval_seconds=1.5)

    assert calls == [None, "fp-1"]
    assert sleep_calls == [1.5, 1.5]


def test_run_forever_logs_and_continues_when_check_and_apply_raises(capsys):
    call_count = 0

    def fake_check(last, profiles_dir):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("xrandr not found")
        return "fp-ok"

    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise _StopLoop()

    with patch("bspwm_display_manager.daemon.watcher.check_and_apply", side_effect=fake_check), \
         patch("bspwm_display_manager.daemon.watcher.time.sleep", side_effect=fake_sleep):
        with pytest.raises(_StopLoop):
            run_forever(Path("/fake/profiles"))

    assert call_count == 2  # the second tick still ran despite the first raising
    assert "xrandr not found" in capsys.readouterr().err
