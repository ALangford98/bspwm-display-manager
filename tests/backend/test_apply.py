import pytest
from unittest.mock import patch

from bspwm_display_manager.backend import reconcile
from bspwm_display_manager.backend.apply import (
    ApplyOutcome, apply_geometry, finish_reconciliation, replay_profile, resolve_targets,
)
from bspwm_display_manager.backend.models import LayoutState, Mode, Output
from bspwm_display_manager.backend.profile import OutputSpec, Profile


def _state():
    dell = Output(name="DP-1", connected=True, primary=False, edid="edid-dell",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    laptop = Output(name="eDP-1", connected=True, primary=True, edid="edid-laptop",
                     x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    return LayoutState(outputs=[dell, laptop])


def _profile():
    return Profile(
        name="work", fingerprint="fp", scale_percent=100,
        outputs=[
            OutputSpec(edid_or_pattern="edid-dell", mode=(2560, 1440), rate=59.95,
                       x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=False),
            OutputSpec(edid_or_pattern="eDP-*", mode=(1920, 1200), rate=60.03,
                       x=2560, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True),
        ],
        desktop_assignment={"edid-dell": ["pm", "office"], "eDP-*": ["term"]},
        hooks=["echo done"],
    )


def test_resolve_targets_matches_by_edid_and_by_name_pattern():
    resolved = resolve_targets(_profile(), _state())
    assert resolved == {"edid-dell": "DP-1", "eDP-*": "eDP-1"}


def test_resolve_targets_raises_when_a_spec_matches_nothing():
    profile = _profile()
    profile.outputs[0].edid_or_pattern = "no-such-edid"
    with pytest.raises(ValueError):
        resolve_targets(profile, _state())


def test_apply_geometry_retires_before_calling_xrandr():
    order_seen = []
    with patch("bspwm_display_manager.backend.apply.reconcile.retire_monitors",
               side_effect=lambda **kw: order_seen.append("retire")), \
         patch("bspwm_display_manager.backend.apply.xrandr_client.apply",
               side_effect=lambda args: order_seen.append("xrandr") or type(
                   "R", (), {"ok": True, "stderr": ""}
               )()):
        outputs = [Output(name="DP-1", connected=True, primary=False, edid=None,
                           x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0,
                           modes=[Mode(2560, 1440, 59.95, "0x1", True, True)])]
        outcome = apply_geometry(outputs, overflow_target="eDP-1", survivors=["DP-1", "eDP-1"])
    assert order_seen == ["retire", "xrandr"]
    assert outcome.ok is True


def test_finish_reconciliation_runs_scale_then_reconcile_then_hooks():
    order_seen = []
    with patch("bspwm_display_manager.backend.apply.apply_scale_env",
               side_effect=lambda p: order_seen.append("scale")), \
         patch("bspwm_display_manager.backend.apply.reconcile.reconcile",
               side_effect=lambda **kw: order_seen.append("reconcile")), \
         patch("bspwm_display_manager.backend.apply.hooks.run_hooks",
               side_effect=lambda cmds: order_seen.append("hooks")):
        outcome = finish_reconciliation(_profile(), {"edid-dell": "DP-1", "eDP-*": "eDP-1"}, ["DP-1", "eDP-1"])
    assert order_seen == ["scale", "reconcile", "hooks"]
    assert outcome.ok is True


def test_finish_reconciliation_returns_failure_outcome_when_reconcile_raises():
    """reconcile.reconcile can raise ReconciliationError (Task 9) --
    finish_reconciliation must catch it and report failure through
    ApplyOutcome rather than letting it propagate as a raw exception
    into the CLI/GUI layers."""
    with patch("bspwm_display_manager.backend.apply.apply_scale_env"), \
         patch("bspwm_display_manager.backend.apply.reconcile.reconcile",
               side_effect=reconcile.ReconciliationError("failed to reorder monitors")), \
         patch("bspwm_display_manager.backend.apply.hooks.run_hooks") as hooks_run:
        outcome = finish_reconciliation(_profile(), {"eDP-*": "eDP-1"}, ["eDP-1"])
    assert outcome.ok is False
    assert "failed to reorder monitors" in outcome.message
    hooks_run.assert_not_called()


def test_apply_geometry_returns_failure_outcome_when_retire_raises():
    with patch("bspwm_display_manager.backend.apply.reconcile.retire_monitors",
               side_effect=reconcile.ReconciliationError("failed to remove monitor 'HDMI-1'")), \
         patch("bspwm_display_manager.backend.apply.xrandr_client.apply") as xrandr_apply:
        outcome = apply_geometry([], overflow_target="eDP-1", survivors=["eDP-1"])
    assert outcome.ok is False
    assert "failed to remove monitor" in outcome.message
    xrandr_apply.assert_not_called()


def test_replay_profile_runs_the_full_pipeline_in_order():
    order_seen = []
    with patch("bspwm_display_manager.backend.apply.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.backend.apply.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.backend.apply.apply_geometry",
               side_effect=lambda *a, **kw: order_seen.append("geometry") or ApplyOutcome(ok=True, message="")), \
         patch("bspwm_display_manager.backend.apply.finish_reconciliation",
               side_effect=lambda *a, **kw: order_seen.append("finish") or ApplyOutcome(ok=True, message="")):
        outcome = replay_profile(_profile())
    assert order_seen == ["geometry", "finish"]
    assert outcome.ok is True


def test_replay_profile_skips_reconciliation_when_geometry_apply_fails():
    with patch("bspwm_display_manager.backend.apply.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.backend.apply.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.backend.apply.apply_geometry",
               return_value=ApplyOutcome(ok=False, message="xrandr: bad mode")), \
         patch("bspwm_display_manager.backend.apply.finish_reconciliation") as finish:
        outcome = replay_profile(_profile())
    finish.assert_not_called()
    assert outcome.ok is False
    assert "bad mode" in outcome.message


def test_replay_profile_returns_finish_reconciliations_outcome():
    with patch("bspwm_display_manager.backend.apply.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.backend.apply.xrandr_parser.parse_verbose", return_value=_state()), \
         patch("bspwm_display_manager.backend.apply.apply_geometry",
               return_value=ApplyOutcome(ok=True, message="")), \
         patch("bspwm_display_manager.backend.apply.finish_reconciliation",
               return_value=ApplyOutcome(ok=False, message="failed to reset padding on 'eDP-1'")):
        outcome = replay_profile(_profile())
    assert outcome.ok is False
    assert "failed to reset padding" in outcome.message
