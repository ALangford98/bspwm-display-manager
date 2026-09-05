from unittest.mock import MagicMock, patch

from bspwm_display_manager.backend.hooks import run_hooks


def test_runs_each_command_through_the_shell_in_order():
    fake = MagicMock(returncode=0, stderr="")
    with patch("subprocess.run", return_value=fake) as run:
        run_hooks(["setsid -f bspbar", "echo hi"])
    assert run.call_args_list[0].args[0] == "setsid -f bspbar"
    assert run.call_args_list[0].kwargs["shell"] is True
    assert run.call_args_list[1].args[0] == "echo hi"


def test_a_failing_hook_does_not_stop_the_rest():
    ok = MagicMock(returncode=0, stderr="")
    fail = MagicMock(returncode=1, stderr="boom")
    with patch("subprocess.run", side_effect=[fail, ok]):
        results = run_hooks(["bad-command", "echo hi"])
    assert results[0].ok is False and results[0].stderr == "boom"
    assert results[1].ok is True


def test_empty_hook_list_runs_nothing():
    with patch("subprocess.run") as run:
        results = run_hooks([])
    run.assert_not_called()
    assert results == []
