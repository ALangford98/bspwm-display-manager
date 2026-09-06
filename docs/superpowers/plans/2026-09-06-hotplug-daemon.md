# Hotplug Daemon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A background daemon that polls the connected monitor set,
fingerprints it, and automatically replays the matching saved profile
(no GUI, no confirm dialog) — so plugging into a dock or undocking
applies the right layout without touching a keyboard shortcut.

**Architecture:** A new Qt-free `daemon/` package built entirely on top
of the already-shipped `backend/` (this plan adds zero new backend
modules — `Profile.fingerprint`, `backend.edid.fingerprint`,
`backend.profile_store`, and `backend.apply.replay_profile` already do
everything needed). A third `daemon` subcommand on the existing CLI, and
a systemd `--user` unit template shipped but not auto-installed.

**Tech Stack:** Python 3.11+, same subprocess-only conventions as the
rest of the project (no python-xlib/libXrandr bindings, no udev
dependency — detection is a polling loop). `notify-send` via subprocess,
best-effort.

**Spec:** `docs/superpowers/specs/2026-09-05-bspwm-display-manager-design.md`
(see the "Hotplug Daemon" component, including its "Implementation"
subsection added for this plan)

## Global Constraints

- Python 3.11+.
- No direct libXrandr/python-xlib/udev bindings — all RandR interaction
  goes through `xrandr` subprocess calls (via the existing
  `backend.xrandr_client`/`backend.xrandr_parser`), notifications
  through `notify-send` subprocess.
- `daemon/` must never import PySide6 — the CLI's `daemon` subcommand
  uses the same lazy-import-inside-the-branch pattern the `gui`
  subcommand already uses, so running `bspwm-display-manager daemon`
  never pulls in Qt.
- Profile JSON lives under `~/.config/bspwm-display-manager/profiles/`
  (`PROFILES_DIR` in `cli.py`, already defined).
- Package layout: `src/bspwm_display_manager/daemon/`, tests under
  `tests/daemon/`.
- A transient failure inside one poll tick must be logged and the loop
  must continue — a systemd service that crash-loops on one bad
  `xrandr` call is worse than one that logs and retries.

---

## Task 1: Best-effort notify-send wrapper

**Files:**
- Create: `src/bspwm_display_manager/daemon/__init__.py` (empty)
- Create: `src/bspwm_display_manager/daemon/notify.py`
- Create: `tests/daemon/__init__.py` (empty)
- Test: `tests/daemon/test_notify.py`

**Interfaces:**
- Produces: `send_notification(title: str, message: str) -> None`
  (never raises, even if `notify-send` isn't installed)

- [ ] **Step 1: Write the failing tests**

```python
# tests/daemon/test_notify.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/daemon/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/daemon/notify.py
from __future__ import annotations

import subprocess
import sys


def send_notification(title: str, message: str) -> None:
    """Best-effort desktop notification. Never raises: a missing or
    failing notify-send must not take down the daemon over UI sugar."""
    try:
        subprocess.run(["notify-send", title, message], check=False)
    except OSError as exc:
        print(f"bspwm-display-manager daemon: notify-send unavailable ({exc})", file=sys.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/daemon/test_notify.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/daemon/__init__.py src/bspwm_display_manager/daemon/notify.py tests/daemon/__init__.py tests/daemon/test_notify.py
git commit -m "$(cat <<'EOF'
Add best-effort notify-send wrapper for the hotplug daemon

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 2: Profile matching by fingerprint

**Files:**
- Create: `src/bspwm_display_manager/daemon/watcher.py`
- Test: `tests/daemon/test_watcher.py`

**Interfaces:**
- Consumes: `Profile` (backend.profile), `profile_store.list_profiles`/`load`
  (backend.profile_store) — both already built, no changes.
- Produces: `find_matching_profile(fingerprint: str, profiles_dir: Path) -> Profile | None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/daemon/test_watcher.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/daemon/watcher.py
from __future__ import annotations

from pathlib import Path

from bspwm_display_manager.backend import profile_store
from bspwm_display_manager.backend.profile import Profile


def find_matching_profile(fingerprint: str, profiles_dir: Path) -> Profile | None:
    for name in profile_store.list_profiles(profiles_dir):
        profile = profile_store.load(name, profiles_dir)
        if profile.fingerprint == fingerprint:
            return profile
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/daemon/watcher.py tests/daemon/test_watcher.py
git commit -m "$(cat <<'EOF'
Add fingerprint-based profile matching for the hotplug daemon

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 3: One poll tick — check_and_apply

**Files:**
- Modify: `src/bspwm_display_manager/daemon/watcher.py`
- Modify: `tests/daemon/test_watcher.py`

**Interfaces:**
- Consumes: `xrandr_client.query_verbose`, `xrandr_parser.parse_verbose`,
  `edid.fingerprint`, `apply.replay_profile` (all backend, already
  built), `find_matching_profile` (Task 2), `notify.send_notification`
  (Task 1).
- Produces: `check_and_apply(last_fingerprint: str | None, profiles_dir: Path) -> str`
  — always returns the newly-observed fingerprint, whether or not
  anything changed, so the caller (Task 4's `run_forever`) can pass it
  back in as `last_fingerprint` on the next tick.

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/daemon/test_watcher.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: FAIL — the 5 new tests fail (missing `check_and_apply` and its
imports); the 3 Task 2 tests still pass.

- [ ] **Step 3: Write the implementation**

```python
# add these imports to the top of src/bspwm_display_manager/daemon/watcher.py,
# replacing the existing import block:
from __future__ import annotations

from pathlib import Path

from bspwm_display_manager.backend import apply, edid, profile_store, xrandr_client, xrandr_parser
from bspwm_display_manager.backend.profile import Profile
from bspwm_display_manager.daemon import notify
```

```python
# appended to src/bspwm_display_manager/daemon/watcher.py, after find_matching_profile:
def check_and_apply(last_fingerprint: str | None, profiles_dir: Path) -> str:
    state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
    current_fingerprint = edid.fingerprint(state.connected())
    if current_fingerprint == last_fingerprint:
        return current_fingerprint

    profile = find_matching_profile(current_fingerprint, profiles_dir)
    if profile is None:
        notify.send_notification(
            "bspwm-display-manager",
            "No saved profile matches the connected displays.",
        )
        return current_fingerprint

    outcome = apply.replay_profile(profile)
    if outcome.ok:
        notify.send_notification("bspwm-display-manager", f"Applied profile {profile.name!r}.")
    else:
        notify.send_notification(
            "bspwm-display-manager", f"Failed to apply {profile.name!r}: {outcome.message}"
        )
    return current_fingerprint
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/daemon/watcher.py tests/daemon/test_watcher.py
git commit -m "$(cat <<'EOF'
Add check_and_apply: one hotplug-daemon poll tick

Queries current xrandr state, and on a fingerprint change (including
daemon startup, where last_fingerprint is None) replays the matching
saved profile or notifies that none matched. Always returns the newly
observed fingerprint so the caller can remember it for the next tick.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 4: The polling loop — run_forever

**Files:**
- Modify: `src/bspwm_display_manager/daemon/watcher.py`
- Modify: `tests/daemon/test_watcher.py`

**Interfaces:**
- Consumes: `check_and_apply` (Task 3).
- Produces: `run_forever(profiles_dir: Path, interval_seconds: float = 3.0) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/daemon/test_watcher.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: FAIL — the 2 new tests fail (missing `run_forever` and the
`time` import); the 8 existing tests still pass.

- [ ] **Step 3: Write the implementation**

```python
# add `import sys` and `import time` to the top of
# src/bspwm_display_manager/daemon/watcher.py's import block, so it reads:
from __future__ import annotations

import sys
import time
from pathlib import Path

from bspwm_display_manager.backend import apply, edid, profile_store, xrandr_client, xrandr_parser
from bspwm_display_manager.backend.profile import Profile
from bspwm_display_manager.daemon import notify
```

```python
# appended to src/bspwm_display_manager/daemon/watcher.py, after check_and_apply:
def run_forever(profiles_dir: Path, interval_seconds: float = 3.0) -> None:
    """Polls check_and_apply on a fixed interval, forever. A transient
    failure in one tick is logged (stdout/stderr, which a systemd user
    service routes to journalctl) and the loop continues -- a
    crash-looping service is worse than one that logs and retries."""
    last_fingerprint: str | None = None
    while True:
        try:
            last_fingerprint = check_and_apply(last_fingerprint, profiles_dir)
        except Exception as exc:
            print(f"bspwm-display-manager daemon: {exc}", file=sys.stderr)
        time.sleep(interval_seconds)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/daemon/test_watcher.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/daemon/watcher.py tests/daemon/test_watcher.py
git commit -m "$(cat <<'EOF'
Add run_forever polling loop for the hotplug daemon

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 5: CLI `daemon` subcommand

**Files:**
- Modify: `src/bspwm_display_manager/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `daemon.watcher.run_forever` (Task 4).
- Produces: `bspwm-display-manager daemon` — runs the polling loop
  against the existing `PROFILES_DIR`, non-interactively.

- [ ] **Step 1: Write the failing test**

```python
# appended to tests/test_cli.py
def test_daemon_runs_run_forever_against_the_profiles_dir():
    with patch("bspwm_display_manager.daemon.watcher.run_forever") as run_forever:
        main(["daemon"])
    run_forever.assert_called_once_with(
        Path.home() / ".config" / "bspwm-display-manager" / "profiles"
    )
```

Note: `daemon` is lazy-imported inside `main()`'s branch as `from
bspwm_display_manager.daemon import watcher as daemon_watcher` (a local
variable, not a module-level attribute of `cli.py`) — so the patch
target must be the function's actual home,
`bspwm_display_manager.daemon.watcher.run_forever`, not
`bspwm_display_manager.cli.daemon_watcher` (that name doesn't exist as a
module attribute; it's purely local to `main()`'s function body, and
`patch()` would fail to find it). Since `daemon_watcher` after the local
import IS the real `bspwm_display_manager.daemon.watcher` module object
(modules are cached/shared via `sys.modules`), patching `run_forever` at
its definition site is seen by `daemon_watcher.run_forever(...)`
regardless of the local alias — this is the same pattern already used
throughout this codebase, e.g. `tests/ui/test_main_window.py` patches
`bspwm_display_manager.ui.main_window.xrandr_client.query_verbose`
rather than any local name inside `main_window.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL — the new test fails (`daemon` command not recognized by
argparse yet, or the patch target doesn't exist); the 4 existing tests
still pass.

- [ ] **Step 3: Modify `cli.py`**

In `src/bspwm_display_manager/cli.py`, add the subparser registration
right after the existing `sub.add_parser("gui", ...)` line:

```python
    sub.add_parser("daemon", help="run the hotplug auto-apply daemon (foreground)")
```

And add the dispatch branch right after the existing `if args.command == "gui":` block, before the trailing `return 1`:

```python
    if args.command == "daemon":
        from bspwm_display_manager.daemon import watcher as daemon_watcher
        daemon_watcher.run_forever(PROFILES_DIR)
        return 0
```

The full file should now read:

```python
# src/bspwm_display_manager/cli.py
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bspwm_display_manager.backend import apply, profile_store

PROFILES_DIR = Path.home() / ".config" / "bspwm-display-manager" / "profiles"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bspwm-display-manager")
    sub = parser.add_subparsers(dest="command", required=True)

    apply_parser = sub.add_parser("apply", help="apply a saved profile by name")
    apply_parser.add_argument("name")

    sub.add_parser("gui", help="launch the GUI")
    sub.add_parser("daemon", help="run the hotplug auto-apply daemon (foreground)")

    args = parser.parse_args(argv)

    if args.command == "apply":
        try:
            profile = profile_store.load(args.name, PROFILES_DIR)
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        try:
            outcome = apply.replay_profile(profile)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if not outcome.ok:
            print(outcome.message, file=sys.stderr)
            return 1
        return 0

    if args.command == "gui":
        from bspwm_display_manager.ui.app import run
        return run()

    if args.command == "daemon":
        from bspwm_display_manager.daemon import watcher as daemon_watcher
        daemon_watcher.run_forever(PROFILES_DIR)
        return 0

    return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full test suite**

Run: `.venv/bin/pytest -v`
Expected: all tests pass (119 from the core plan + this plan's new
tests, around 135 total — the exact count isn't load-bearing, just
confirm zero failures).

- [ ] **Step 6: Verify the console script's daemon subcommand resolves**

Run: `.venv/bin/pip install -e . && timeout 4 .venv/bin/bspwm-display-manager daemon; echo "exit: $?"`
Expected: runs for ~4 seconds (one or more real poll ticks against
whatever's actually connected on this machine), then `timeout` kills it
(exit code 124) — confirms the command starts, doesn't crash
immediately, and doesn't import PySide6 (no Qt-related error even
though this environment has PySide6 installed from the core plan — the
point is it *wouldn't* need to be installed).

- [ ] **Step 7: Commit**

```bash
git add src/bspwm_display_manager/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
Add daemon CLI subcommand

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 6: systemd unit template + README

**Files:**
- Create: `packaging/bspwm-display-manager-daemon.service`
- Modify: `README.md`

**Interfaces:**
- Produces: no code; a systemd `--user` unit template and documentation
  for enabling it.

- [ ] **Step 1: Write the systemd unit template**

```ini
# packaging/bspwm-display-manager-daemon.service
[Unit]
Description=bspwm-display-manager hotplug auto-apply daemon
After=graphical-session.target

[Service]
# Replace this with the absolute path to this project's venv --
# systemd user services do not inherit your interactive shell's PATH,
# so the bare command name will not resolve (same reason the sxhkd
# migration example in this README uses an absolute path).
ExecStart=/path/to/bspwm-display-manager/.venv/bin/bspwm-display-manager daemon
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

- [ ] **Step 2: Add a README section**

Insert a new `## Hotplug auto-apply (optional)` section into
`README.md`, immediately after the existing `## Session-wide scale`
section and before `## Migrating from hand-written screenlayout
scripts`:

```markdown
## Hotplug auto-apply (optional)

`bspwm-display-manager daemon` runs in the foreground, polling the
connected monitors every few seconds. When the set of connected
displays changes (a dock connect/disconnect, a monitor power cycle) it
automatically replays whichever saved profile's fingerprint matches —
no keyboard shortcut needed. If nothing matches, it leaves your current
layout alone and sends a desktop notification rather than guessing.

To run it automatically at login via systemd:

    mkdir -p ~/.config/systemd/user
    cp packaging/bspwm-display-manager-daemon.service ~/.config/systemd/user/
    # edit the ExecStart line in that file to point at this project's
    # actual .venv/bin/bspwm-display-manager path
    systemctl --user daemon-reload
    systemctl --user enable --now bspwm-display-manager-daemon

Check on it with:

    systemctl --user status bspwm-display-manager-daemon
    journalctl --user -u bspwm-display-manager-daemon -f

This is entirely optional — `bspwm-display-manager apply <name>` from a
keyboard shortcut works fine without the daemon running at all.
```

- [ ] **Step 3: Self-review**

Read back both files. Confirm: the `.service` file's `ExecStart` comment
clearly says it's a placeholder that must be edited (do not leave a path
that looks like it might already work), the README commands are exact
and in the right order (`daemon-reload` before `enable --now`), and the
new section doesn't duplicate anything already said in "Session-wide
scale" or "Migrating from hand-written screenlayout scripts".

- [ ] **Step 4: Commit**

```bash
git add packaging/bspwm-display-manager-daemon.service README.md
git commit -m "$(cat <<'EOF'
Add systemd unit template and README section for the hotplug daemon

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** polling detection (Task 4), the
`find_matching_profile`/`check_and_apply` split reusing
`Profile.fingerprint`/`backend.edid.fingerprint`/`backend.apply.replay_profile`
(Tasks 2-3), best-effort `notify-send` (Task 1), failure logging that
keeps the loop alive (Task 4), the `daemon` CLI subcommand with the same
lazy-Qt-import pattern as `gui` (Task 5), the systemd template with a
deliberately-placeholder `ExecStart` (Task 6). Event-driven/udev
detection is explicitly out of scope per the spec's Implementation
subsection — not a gap in this plan.

**Type consistency check:** `find_matching_profile` returns `Profile |
None` and `check_and_apply` returns `str` in both Task 2/3's own text
and every later reference to them (Task 4's `run_forever`, Task 5's
CLI dispatch) — consistent throughout. `notify.send_notification`'s two
positional string args match every call site in `watcher.py`.

**Placeholder scan:** no TODO/TBD; every step has runnable code or, for
Task 6, a complete unit file and complete README prose.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-06-hotplug-daemon.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per
task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using
executing-plans, batch execution with checkpoints.

**Which approach?**