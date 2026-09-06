from unittest.mock import patch

from bspwm_display_manager.daemon.notify import send_notification


def test_send_notification_runs_notify_send_with_title_and_message():
    with patch("subprocess.run") as run:
        send_notification("bspwm-display-manager", "Applied profile 'work'.")
    run.assert_called_once_with(
        ["notify-send", "bspwm-display-manager", "Applied profile 'work'."], check=False
    )


def test_send_notification_does_not_raise_when_notify_send_is_missing(capsys):
    with patch("subprocess.run", side_effect=FileNotFoundError("no such file: notify-send")):
        send_notification("Title", "Body")  # must not raise
    assert "notify-send" in capsys.readouterr().err


def test_send_notification_does_not_raise_on_a_generic_os_error(capsys):
    with patch("subprocess.run", side_effect=OSError("permission denied")):
        send_notification("Title", "Body")  # must not raise
    assert "permission denied" in capsys.readouterr().err
