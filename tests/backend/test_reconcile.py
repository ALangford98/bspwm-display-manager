from unittest.mock import MagicMock, patch

import pytest

from bspwm_display_manager.backend import reconcile as rc


def test_retire_monitors_adds_placeholder_before_moving_desktops():
    """The last-desktop-move-refusal workaround: a placeholder desktop
    must exist on the doomed monitor before any real desktop is moved
    off it, so no real desktop is ever "the last one" being moved."""
    calls = []

    def _track(tag):
        # Records the call AND reports success (True) -- bspc_client's
        # mutating functions return bool, and reconcile.py now raises on
        # a False, so every mock standing in for a "this call succeeded"
        # scenario must return True, not None.
        def _fn(*args):
            calls.append((tag, *args))
            return True
        return _fn

    with patch("bspwm_display_manager.backend.reconcile.bspc_client.query_monitor_names",
               return_value=["eDP-1", "HDMI-1"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.add_desktop",
               side_effect=_track("add_desktop")), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.query_desktop_names",
               return_value=["ide1", "ide2", "__bsp_retiring__"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.move_desktop_to_monitor",
               side_effect=_track("move")), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.remove_monitor",
               side_effect=_track("remove_monitor")):
        rc.retire_monitors(overflow_target="eDP-1", survivors=["eDP-1"])

    assert calls[0] == ("add_desktop", "HDMI-1", "__bsp_retiring__")
    assert ("move", "ide1", "eDP-1") in calls
    assert ("move", "ide2", "eDP-1") in calls
    assert ("move", "__bsp_retiring__", "eDP-1") not in calls
    assert calls[-1] == ("remove_monitor", "HDMI-1")


def test_retire_monitors_leaves_surviving_monitors_alone():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.query_monitor_names",
               return_value=["eDP-1", "DP-1"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.add_desktop") as add, \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.remove_monitor") as remove:
        rc.retire_monitors(overflow_target="eDP-1", survivors=["eDP-1", "DP-1"])
    add.assert_not_called()
    remove.assert_not_called()


def test_assign_desktops_moves_an_existing_desktop_by_identity():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.desktop_exists", return_value=True), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.move_desktop_to_monitor") as move, \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.add_desktop") as add:
        rc.assign_desktops("DP-1", ["pm", "office"])
    assert move.call_args_list == [(("pm", "DP-1"),), (("office", "DP-1"),)]
    add.assert_not_called()


def test_assign_desktops_adds_a_desktop_that_does_not_exist_yet():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.desktop_exists", return_value=False), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.add_desktop") as add, \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.move_desktop_to_monitor") as move:
        rc.assign_desktops("DP-1", ["ide1"])
    add.assert_called_once_with("DP-1", "ide1")
    move.assert_not_called()


def test_assign_desktops_never_calls_bspc_monitor_dash_d():
    """Regression guard for the documented bug: `bspc monitor -d <fewer
    names>` silently folds dropped desktops into the last name in the new
    list instead of handing them to another monitor. This module must
    never construct that call at all. Deliberately does NOT mock
    bspc_client's functions — only the true subprocess boundary — so the
    real desktop_exists/move_desktop_to_monitor/add_desktop code paths
    run and their real argv reaches this assertion; mocking bspc_client
    itself here would make the assertion vacuous (nothing would ever
    reach `-d` no matter what assign_desktops did).

    A plain `return_value=` stub (returncode=0 for every call) would
    make `desktop_exists` report every name as existing, so only the
    `--to-monitor` branch would ever run and the `-a` (create) branch —
    the exact branch a `-a` vs `-d` typo would land in — would go
    completely unexercised, closing a coverage gap without noticing.
    This `side_effect` makes 'settings' report as not-existing so the
    create branch genuinely executes too, under the same assertion."""
    def _fake_run(argv, **kwargs):
        if argv[:4] == ["bspc", "query", "-D", "-d"] and argv[4] == "settings":
            return MagicMock(returncode=1, stdout="", stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")

    with patch("subprocess.run", side_effect=_fake_run) as run:
        rc.assign_desktops("DP-1", ["pm", "office", "settings"])
    calls = [call.args[0] for call in run.call_args_list]
    assert ["bspc", "desktop", "pm", "--to-monitor", "DP-1"] in calls
    assert ["bspc", "monitor", "DP-1", "-a", "settings"] in calls  # confirms the create branch ran
    for argv in calls:
        assert not (argv[:2] == ["bspc", "monitor"] and "-d" in argv)


def test_sweep_placeholder_desktops_removes_only_empty_unexpected_ones():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.query_desktop_names",
               return_value=["term", "chat", "Desktop"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.desktop_is_empty",
               side_effect=lambda name: name == "Desktop"), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.remove_desktop") as remove:
        rc.sweep_placeholder_desktops(expected_names={"term", "chat"})
    remove.assert_called_once_with("Desktop")


def test_sweep_placeholder_desktops_never_removes_a_nonempty_stray():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.query_desktop_names",
               return_value=["term", "Desktop"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.desktop_is_empty",
               return_value=False), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.remove_desktop") as remove:
        rc.sweep_placeholder_desktops(expected_names={"term"})
    remove.assert_not_called()


def test_reset_active_padding_resets_every_active_monitor():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.reset_padding") as reset:
        rc.reset_active_padding(["eDP-1", "DP-1"])
    assert reset.call_args_list == [(("eDP-1",),), (("DP-1",),)]


def test_reconcile_runs_padding_then_assignment_then_reorder_then_sweep():
    order_seen = []
    with patch("bspwm_display_manager.backend.reconcile.reset_active_padding",
               side_effect=lambda mons: order_seen.append("padding")), \
         patch("bspwm_display_manager.backend.reconcile.assign_desktops",
               side_effect=lambda t, n: order_seen.append("assign")), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.reorder_monitors",
               side_effect=lambda o: order_seen.append("reorder") or True), \
         patch("bspwm_display_manager.backend.reconcile.sweep_placeholder_desktops",
               side_effect=lambda names: order_seen.append("sweep")):
        rc.reconcile(
            active_monitors=["eDP-1", "DP-1"],
            desktop_assignment={"DP-1": ["pm"], "eDP-1": ["term"]},
            order=["DP-1", "eDP-1"],
        )
    assert order_seen == ["padding", "assign", "assign", "reorder", "sweep"]


def test_retire_monitors_raises_when_add_desktop_fails():
    """A failed bspc call must stop this function rather than proceeding
    to move desktops off a monitor whose placeholder was never actually
    created."""
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.query_monitor_names",
               return_value=["eDP-1", "HDMI-1"]), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.add_desktop", return_value=False), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.query_desktop_names") as query, \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.remove_monitor") as remove:
        with pytest.raises(rc.ReconciliationError):
            rc.retire_monitors(overflow_target="eDP-1", survivors=["eDP-1"])
    query.assert_not_called()
    remove.assert_not_called()


def test_assign_desktops_raises_when_move_fails():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.desktop_exists", return_value=True), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.move_desktop_to_monitor",
               return_value=False):
        with pytest.raises(rc.ReconciliationError):
            rc.assign_desktops("DP-1", ["pm"])


def test_reset_active_padding_raises_when_reset_padding_fails():
    with patch("bspwm_display_manager.backend.reconcile.bspc_client.reset_padding",
               return_value=False):
        with pytest.raises(rc.ReconciliationError):
            rc.reset_active_padding(["eDP-1"])


def test_reconcile_raises_when_reorder_fails():
    with patch("bspwm_display_manager.backend.reconcile.reset_active_padding"), \
         patch("bspwm_display_manager.backend.reconcile.assign_desktops"), \
         patch("bspwm_display_manager.backend.reconcile.bspc_client.reorder_monitors",
               return_value=False), \
         patch("bspwm_display_manager.backend.reconcile.sweep_placeholder_desktops") as sweep:
        with pytest.raises(rc.ReconciliationError):
            rc.reconcile(active_monitors=["eDP-1"], desktop_assignment={"eDP-1": ["term"]}, order=["eDP-1"])
    sweep.assert_not_called()
