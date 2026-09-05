import subprocess
from unittest.mock import patch, MagicMock

from bspwm_display_manager.backend.xrandr_client import apply, query_verbose


def test_query_verbose_runs_xrandr_verbose_and_returns_stdout():
    fake = MagicMock(stdout="Screen 0: ...\n", returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        text = query_verbose()
    run.assert_called_once_with(
        ["xrandr", "--verbose"], capture_output=True, text=True, check=False
    )
    assert text == "Screen 0: ...\n"


def test_apply_runs_xrandr_with_given_args_and_reports_success():
    fake = MagicMock(returncode=0, stderr="")
    with patch("subprocess.run", return_value=fake) as run:
        result = apply(["--output", "eDP-1", "--mode", "1920x1200"])
    run.assert_called_once_with(
        ["xrandr", "--output", "eDP-1", "--mode", "1920x1200"],
        capture_output=True, text=True, check=False,
    )
    assert result.ok is True
    assert result.returncode == 0


def test_apply_reports_failure_on_nonzero_exit():
    fake = MagicMock(returncode=1, stderr="xrandr: cannot find mode\n")
    with patch("subprocess.run", return_value=fake):
        result = apply(["--output", "DP-9", "--mode", "9999x9999"])
    assert result.ok is False
    assert result.returncode == 1
    assert "cannot find mode" in result.stderr
