from pathlib import Path
from unittest.mock import patch

from bspwm_display_manager.cli import main


def test_apply_loads_named_profile_and_replays_it(tmp_path, capsys):
    fake_profile = object()
    with patch("bspwm_display_manager.cli.profile_store.load", return_value=fake_profile) as load, \
         patch("bspwm_display_manager.cli.apply.replay_profile") as replay:
        replay.return_value = type("O", (), {"ok": True, "message": ""})()
        code = main(["apply", "work"])
    load.assert_called_once_with("work", Path.home() / ".config" / "bspwm-display-manager" / "profiles")
    replay.assert_called_once_with(fake_profile)
    assert code == 0


def test_apply_prints_error_and_returns_nonzero_on_failure(capsys):
    with patch("bspwm_display_manager.cli.profile_store.load", return_value=object()), \
         patch("bspwm_display_manager.cli.apply.replay_profile") as replay:
        replay.return_value = type("O", (), {"ok": False, "message": "xrandr: bad mode"})()
        code = main(["apply", "work"])
    assert code == 1
    assert "bad mode" in capsys.readouterr().err


def test_apply_missing_profile_returns_nonzero(capsys):
    with patch("bspwm_display_manager.cli.profile_store.load", side_effect=FileNotFoundError("no profile")):
        code = main(["apply", "nonexistent"])
    assert code == 1
    assert "no profile" in capsys.readouterr().err


def test_apply_prints_error_when_profile_outputs_do_not_match_connected_monitors(capsys):
    """E.g. running `apply work` while undocked — resolve_targets raises
    ValueError instead of returning an ApplyOutcome. Must not be an
    uncaught traceback on a keyboard shortcut."""
    with patch("bspwm_display_manager.cli.profile_store.load", return_value=object()), \
         patch("bspwm_display_manager.cli.apply.replay_profile",
               side_effect=ValueError("no connected output matches 'edid-dell'")):
        code = main(["apply", "work"])
    assert code == 1
    assert "no connected output matches" in capsys.readouterr().err


def test_daemon_runs_run_forever_against_the_profiles_dir():
    with patch("bspwm_display_manager.daemon.watcher.run_forever") as run_forever:
        main(["daemon"])
    run_forever.assert_called_once_with(
        Path.home() / ".config" / "bspwm-display-manager" / "profiles"
    )
