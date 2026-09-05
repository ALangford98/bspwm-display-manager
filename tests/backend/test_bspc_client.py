from unittest.mock import MagicMock, patch

from bspwm_display_manager.backend import bspc_client as bc


def test_query_monitor_names_splits_lines():
    fake = MagicMock(stdout="eDP-1\nDP-1\n", returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        names = bc.query_monitor_names()
    run.assert_called_once_with(
        ["bspc", "query", "-M", "--names"], capture_output=True, text=True, check=False
    )
    assert names == ["eDP-1", "DP-1"]


def test_query_desktop_names_without_monitor():
    fake = MagicMock(stdout="term\nchat\n", returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        names = bc.query_desktop_names()
    run.assert_called_once_with(
        ["bspc", "query", "-D", "--names"], capture_output=True, text=True, check=False
    )
    assert names == ["term", "chat"]


def test_query_desktop_names_scoped_to_monitor():
    fake = MagicMock(stdout="pm\noffice\n", returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        names = bc.query_desktop_names(monitor="DP-1")
    run.assert_called_once_with(
        ["bspc", "query", "-D", "-m", "DP-1", "--names"], capture_output=True, text=True, check=False
    )
    assert names == ["pm", "office"]


def test_desktop_exists_true_on_zero_exit():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        assert bc.desktop_exists("term") is True
    run.assert_called_once_with(
        ["bspc", "query", "-D", "-d", "term"], capture_output=True, text=True, check=False
    )


def test_desktop_exists_false_on_nonzero_exit():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.desktop_exists("ghost") is False


def test_desktop_is_empty_true_when_no_window_node_matches():
    fake = MagicMock(stdout="", returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        assert bc.desktop_is_empty("ide1") is True
    run.assert_called_once_with(
        ["bspc", "query", "-N", "-d", "ide1", "-n", ".window"],
        capture_output=True, text=True, check=False,
    )


def test_desktop_is_empty_false_when_a_window_node_matches():
    fake = MagicMock(stdout="0x02000123\n", returncode=0)
    with patch("subprocess.run", return_value=fake):
        assert bc.desktop_is_empty("ide1") is False


def test_move_desktop_to_monitor():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.move_desktop_to_monitor("pm", "DP-1")  # capture the return value
    run.assert_called_once_with(
        ["bspc", "desktop", "pm", "--to-monitor", "DP-1"], capture_output=True, text=True, check=False
    )
    assert result is True  # NEW assertion


def test_move_desktop_to_monitor_returns_false_on_failure():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.move_desktop_to_monitor("pm", "DP-1") is False


def test_add_desktop():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.add_desktop("DP-1", "pm")  # capture the return value
    run.assert_called_once_with(
        ["bspc", "monitor", "DP-1", "-a", "pm"], capture_output=True, text=True, check=False
    )
    assert result is True  # NEW assertion


def test_add_desktop_returns_false_on_failure():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.add_desktop("DP-1", "pm") is False


def test_remove_desktop():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.remove_desktop("ghost")  # capture the return value
    run.assert_called_once_with(
        ["bspc", "desktop", "ghost", "-r"], capture_output=True, text=True, check=False
    )
    assert result is True  # NEW assertion


def test_remove_desktop_returns_false_on_failure():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.remove_desktop("ghost") is False


def test_remove_monitor():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.remove_monitor("HDMI-1")  # capture the return value
    run.assert_called_once_with(
        ["bspc", "monitor", "HDMI-1", "-r"], capture_output=True, text=True, check=False
    )
    assert result is True  # NEW assertion


def test_remove_monitor_returns_false_on_failure():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.remove_monitor("HDMI-1") is False


def test_reset_padding_sets_all_four_edges_to_zero():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.reset_padding("eDP-1")  # capture the return value
    assert run.call_count == 4
    calls = [c.args[0] for c in run.call_args_list]
    for edge in ("top_padding", "bottom_padding", "left_padding", "right_padding"):
        assert ["bspc", "config", "-m", "eDP-1", edge, "0"] in calls
    assert result is True  # NEW assertion


def test_reset_padding_returns_false_if_any_edge_fails():
    ok = MagicMock(returncode=0)
    fail = MagicMock(returncode=1)
    with patch("subprocess.run", side_effect=[ok, ok, fail, ok]):
        assert bc.reset_padding("eDP-1") is False


def test_reorder_monitors():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        result = bc.reorder_monitors(["DP-1", "eDP-1", "DP-2"])  # capture the return value
    run.assert_called_once_with(
        ["bspc", "wm", "-O", "DP-1", "eDP-1", "DP-2"], capture_output=True, text=True, check=False
    )
    assert result is True  # NEW assertion


def test_reorder_monitors_returns_false_on_failure():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert bc.reorder_monitors(["DP-1"]) is False
