from pathlib import Path
from unittest.mock import patch

import pytest

from bspwm_display_manager.backend import reconcile
from bspwm_display_manager.backend.apply import (
    ApplyOutcome, apply_geometry, apply_scale_env, finish_reconciliation, replay_profile, resolve_targets,
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
    into the CLI/GUI layers. `resolved` must cover every key in
    _profile()'s desktop_assignment (edid-dell AND eDP-*) -- in the real
    pipeline resolve_targets() guarantees this for every key that
    appears in profile.outputs (and desktop_assignment keys are always a
    subset of those), so finish_reconciliation's dict comprehension is
    entitled to assume it; passing a partial resolved dict here would
    raise KeyError before reconcile.reconcile is ever reached, which
    would test the wrong thing."""
    with patch("bspwm_display_manager.backend.apply.apply_scale_env"), \
         patch("bspwm_display_manager.backend.apply.reconcile.reconcile",
               side_effect=reconcile.ReconciliationError("failed to reorder monitors")), \
         patch("bspwm_display_manager.backend.apply.hooks.run_hooks") as hooks_run:
        outcome = finish_reconciliation(
            _profile(), {"edid-dell": "DP-1", "eDP-*": "eDP-1"}, ["DP-1", "eDP-1"]
        )
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


def test_apply_geometry_returns_failure_outcome_when_xrandr_apply_raises():
    """ApplyOutcome is the whole contract Task 18's GUI gates on -- an
    OSError (e.g. the xrandr binary itself is missing) must not escape
    as a raw exception any more than a ReconciliationError may."""
    with patch("bspwm_display_manager.backend.apply.reconcile.retire_monitors"), \
         patch("bspwm_display_manager.backend.apply.xrandr_client.apply",
               side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'xrandr'")):
        outcome = apply_geometry([], overflow_target="eDP-1", survivors=["eDP-1"])
    assert outcome.ok is False
    assert "xrandr" in outcome.message


def test_finish_reconciliation_returns_failure_outcome_when_apply_scale_env_raises():
    """Same contract for finish_reconciliation: apply_scale_env writes a
    real file and shells out to xrdb, both of which can raise OSError
    (e.g. permission denied, xrdb missing)."""
    with patch("bspwm_display_manager.backend.apply.apply_scale_env",
               side_effect=OSError("[Errno 13] Permission denied")), \
         patch("bspwm_display_manager.backend.apply.reconcile.reconcile") as reconcile_fn, \
         patch("bspwm_display_manager.backend.apply.hooks.run_hooks") as hooks_run:
        outcome = finish_reconciliation(
            _profile(), {"edid-dell": "DP-1", "eDP-*": "eDP-1"}, ["DP-1", "eDP-1"]
        )
    assert outcome.ok is False
    assert "Permission denied" in outcome.message
    reconcile_fn.assert_not_called()
    hooks_run.assert_not_called()


def test_finish_reconciliation_returns_failure_outcome_when_resolved_is_missing_a_desktop_assignment_key():
    """A hand-edited or stale profile could have a desktop_assignment
    key that resolve_targets never produced. Must not raise a raw
    KeyError -- report it through ApplyOutcome like every other failure
    in this function."""
    with patch("bspwm_display_manager.backend.apply.apply_scale_env"):
        outcome = finish_reconciliation(_profile(), {"eDP-*": "eDP-1"}, ["eDP-1"])
    assert outcome.ok is False
    assert "edid-dell" in outcome.message


def test_replay_profile_turns_off_connected_outputs_not_in_the_profile():
    """A profile that only lists eDP-1 (home) must explicitly turn off
    any other connected output (e.g. DP-1, still physically connected
    while docked) -- otherwise it stays live in X even though its bspwm
    monitor was just retired."""
    state = LayoutState(outputs=[
        Output(name="eDP-1", connected=True, primary=True, edid="edid-laptop",
               x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[]),
        Output(name="DP-1", connected=True, primary=False, edid="edid-dell",
               x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[]),
    ])
    home_profile = Profile(
        name="home", fingerprint="fp", scale_percent=100,
        outputs=[OutputSpec(edid_or_pattern="edid-laptop", mode=(1920, 1200), rate=60.03,
                             x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True)],
        desktop_assignment={"edid-laptop": ["term"]}, hooks=[],
    )
    captured = {}
    with patch("bspwm_display_manager.backend.apply.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.backend.apply.xrandr_parser.parse_verbose", return_value=state), \
         patch("bspwm_display_manager.backend.apply.reconcile.retire_monitors"), \
         patch("bspwm_display_manager.backend.apply.command_builder.build_xrandr_args",
               side_effect=lambda outs: captured.setdefault("outputs", outs) or []), \
         patch("bspwm_display_manager.backend.apply.xrandr_client.apply",
               return_value=type("R", (), {"ok": True, "stderr": ""})()), \
         patch("bspwm_display_manager.backend.apply.finish_reconciliation",
               return_value=ApplyOutcome(ok=True, message="")):
        replay_profile(home_profile)
    off_names = [o.name for o in captured["outputs"] if not o.modes]
    assert off_names == ["DP-1"]


def test_replay_profile_returns_failure_outcome_when_no_output_is_primary():
    profile = _profile()
    for spec in profile.outputs:
        spec.primary = False
    with patch("bspwm_display_manager.backend.apply.xrandr_client.query_verbose", return_value=""), \
         patch("bspwm_display_manager.backend.apply.xrandr_parser.parse_verbose", return_value=_state()):
        outcome = replay_profile(profile)
    assert outcome.ok is False
    assert "primary" in outcome.message


def test_apply_scale_env_writes_env_file_and_merges_xft_dpi_via_xrdb(tmp_path, monkeypatch):
    """The only test that actually exercises apply_scale_env's body --
    every other test in this file patches it out, since it's the one
    function here with real side effects (a real file write, a real
    subprocess call to xrdb). Redirects HOME to tmp_path and mocks
    subprocess.run so this never touches the real machine, however this
    test is invoked."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    with patch("bspwm_display_manager.backend.apply.subprocess.run") as run:
        apply_scale_env(150)

    run.assert_called_once_with(
        ["xrdb", "-merge"], input="Xft.dpi: 144\n", text=True, check=False
    )
    env_file = tmp_path / ".config" / "bspwm-display-manager" / "env"
    content = env_file.read_text()
    assert "export GDK_SCALE=1.5\n" in content
    assert "export QT_SCALE_FACTOR=1.5\n" in content
    assert "export QT_AUTO_SCREEN_SCALE_FACTOR=0\n" in content
    assert "Xft.dpi" not in content  # Xft.dpi goes to xrdb, not the env file
