# bspwm-display-manager Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PySide6 GUI (plus a CLI) that lets the user drag-arrange
bspwm's connected displays, set mode/refresh/scale, assign bspwm desktops
to monitors, and save/replay named profiles (`work`, `home`) — replacing
`~/.screenlayout/{work,home}-layout.sh` and the `bsp-assign-desktops` /
`bsp-retire-monitors` scripts with a generalized, GUI-editable equivalent.

**Architecture:** Three layers — `backend/` (pure Python: RandR parsing,
command building, EDID fingerprinting, profile persistence, bspc
reconciliation), `ui/` (PySide6 widgets consuming the backend), `cli.py`
(argparse entry point for `apply <profile>`, used by sxhkd keybindings,
and `gui`). The hotplug daemon (auto-apply on physical connect/disconnect)
is an intentionally separate follow-up plan — this plan's deliverable is
a fully working manual-apply GUI + instant CLI apply, which alone
replaces the two keybindings.

**Tech Stack:** Python 3.11+, PySide6, pytest. `xrandr` and `bspc`
invoked via `subprocess`, never bound directly (matches how
`arandr`/`autorandr` do it, robust to X server/bspwm version drift).

**Spec:** `docs/superpowers/specs/2026-09-05-bspwm-display-manager-design.md`

## Global Constraints

- Python 3.11+ (uses `X | Y` union syntax, `tomllib`).
- No direct libXrandr/python-xlib bindings — all RandR interaction goes
  through `xrandr` subprocess calls; all bspwm interaction goes through
  `bspc` subprocess calls.
- Every function that shells out to `xrandr` or `bspc` takes the argv
  list (or a thin wrapper) as its unit of testing — tests assert on the
  constructed argv, never on a real subprocess result, per the spec's
  "no real bspc/xrandr calls in automated tests" rule.
- Profile JSON lives under `~/.config/bspwm-display-manager/profiles/`.
- Package layout: `src/bspwm_display_manager/{backend,ui}/`, tests under
  `tests/{backend,ui}/`, fixtures under `tests/fixtures/`.
- Two `xrandr --verbose` fixtures already exist:
  `tests/fixtures/xrandr_verbose_single_laptop.txt` (this machine, one
  connected output `eDP-1`, two disconnected) and
  `tests/fixtures/xrandr_verbose_dual_office.txt` (synthetic: `eDP-1`
  primary bottom-center, `DP-1` 2560x1440 top-left, `DP-2` connected at
  2560x1440 but with a `3840x2160 +preferred` mode also listed — the
  scaled-4K-panel case from `work-layout.sh`).

---

## Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `src/bspwm_display_manager/__init__.py`
- Create: `src/bspwm_display_manager/backend/__init__.py`
- Create: `src/bspwm_display_manager/ui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/backend/__init__.py`
- Create: `tests/ui/__init__.py`

**Interfaces:**
- Produces: an installable package `bspwm_display_manager` importable
  from `backend.*` and `ui.*`; `pytest` runnable from the project root.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "bspwm-display-manager"
version = "0.1.0"
description = "GUI + CLI for arranging bspwm displays and desktop-to-monitor assignment"
requires-python = ">=3.11"
license = { text = "MIT" }
dependencies = [
    "PySide6>=6.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[project.scripts]
bspwm-display-manager = "bspwm_display_manager.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.venv/
*.egg-info/
build/
dist/
.pytest_cache/
```

- [ ] **Step 3: Write `LICENSE`**

```
MIT License

Copyright (c) 2026 Anthony

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Create empty package/test `__init__.py` files**

All nine files listed under Files are empty (0 bytes) except
`pyproject.toml`, `.gitignore`, and `LICENSE` above.

- [ ] **Step 5: Install in editable/dev mode and verify**

Run: `cd ~/Documents/bspwm-display-manager && python -m venv .venv && .venv/bin/pip install -e ".[dev]"`
Expected: install succeeds, `PySide6` and `pytest` both resolve.

Run: `.venv/bin/pytest`
Expected: `no tests ran` (or `collected 0 items`), exit code 0.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .gitignore LICENSE src tests
git commit -m "$(cat <<'EOF'
Scaffold Python package for bspwm-display-manager

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 2: Core data models

**Files:**
- Create: `src/bspwm_display_manager/backend/models.py`
- Test: `tests/backend/test_models.py`

**Interfaces:**
- Produces:
  - `Mode(width: int, height: int, rate: float, id: str, current: bool, preferred: bool)`
  - `Output(name: str, connected: bool, primary: bool, edid: str | None, x: int, y: int, rotation: str, scale_x: float, scale_y: float, modes: list[Mode])`
    - `Output.current_mode() -> Mode | None`
    - `Output.preferred_mode() -> Mode | None`
  - `LayoutState(outputs: list[Output])`
    - `LayoutState.connected() -> list[Output]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_models.py
from bspwm_display_manager.backend.models import Mode, Output, LayoutState

def test_output_current_mode_returns_the_starred_mode():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=True, preferred=True)
    m2 = Mode(width=1920, height=1200, rate=59.88, id="0x4a", current=False, preferred=False)
    out = Output(name="eDP-1", connected=True, primary=True, edid="abc",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0,
                 modes=[m1, m2])
    assert out.current_mode() is m1

def test_output_current_mode_none_when_no_mode_is_current():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=False, preferred=True)
    out = Output(name="HDMI-1", connected=False, primary=False, edid=None,
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[m1])
    assert out.current_mode() is None

def test_output_preferred_mode_returns_the_plus_preferred_mode():
    m1 = Mode(width=1920, height=1200, rate=60.03, id="0x49", current=True, preferred=False)
    m2 = Mode(width=3840, height=2160, rate=59.98, id="0x4c", current=False, preferred=True)
    out = Output(name="DP-2", connected=True, primary=False, edid="xyz",
                 x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0,
                 modes=[m1, m2])
    assert out.preferred_mode() is m2

def test_layout_state_connected_filters_disconnected_outputs():
    connected = Output(name="eDP-1", connected=True, primary=True, edid="a",
                        x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    disconnected = Output(name="HDMI-1", connected=False, primary=False, edid=None,
                           x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])
    state = LayoutState(outputs=[connected, disconnected])
    assert state.connected() == [connected]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bspwm_display_manager.backend.models'`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/models.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mode:
    width: int
    height: int
    rate: float
    id: str
    current: bool
    preferred: bool


@dataclass
class Output:
    name: str
    connected: bool
    primary: bool
    edid: str | None
    x: int
    y: int
    rotation: str
    scale_x: float
    scale_y: float
    modes: list[Mode] = field(default_factory=list)

    def current_mode(self) -> Mode | None:
        return next((m for m in self.modes if m.current), None)

    def preferred_mode(self) -> Mode | None:
        return next((m for m in self.modes if m.preferred), None)


@dataclass
class LayoutState:
    outputs: list[Output] = field(default_factory=list)

    def connected(self) -> list[Output]:
        return [o for o in self.outputs if o.connected]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_models.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/models.py tests/backend/test_models.py
git commit -m "$(cat <<'EOF'
Add Mode/Output/LayoutState data models

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 3: xrandr --verbose parser

**Files:**
- Create: `src/bspwm_display_manager/backend/xrandr_parser.py`
- Test: `tests/backend/test_xrandr_parser.py`
- Uses fixtures: `tests/fixtures/xrandr_verbose_single_laptop.txt`,
  `tests/fixtures/xrandr_verbose_dual_office.txt`

**Interfaces:**
- Consumes: `Mode`, `Output`, `LayoutState` from Task 2 (`bspwm_display_manager.backend.models`).
- Produces: `parse_verbose(text: str) -> LayoutState`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_xrandr_parser.py
from pathlib import Path

from bspwm_display_manager.backend.xrandr_parser import parse_verbose

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_parses_single_connected_laptop_output():
    text = (FIXTURES / "xrandr_verbose_single_laptop.txt").read_text()
    state = parse_verbose(text)
    connected = state.connected()
    assert [o.name for o in connected] == ["eDP-1"]

    edp = connected[0]
    assert edp.primary is True
    assert edp.x == 0 and edp.y == 0
    assert edp.edid is not None and edp.edid.startswith("00ffffffffffff")
    cur = edp.current_mode()
    assert (cur.width, cur.height, cur.rate) == (1920, 1200, 60.03)
    assert cur.preferred is True


def test_disconnected_outputs_are_present_but_not_connected():
    text = (FIXTURES / "xrandr_verbose_single_laptop.txt").read_text()
    state = parse_verbose(text)
    names = {o.name: o.connected for o in state.outputs}
    assert names == {"eDP-1": True, "HDMI-1": False, "DP-1": False}


def test_parses_three_connected_outputs_with_positions():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    by_name = {o.name: o for o in state.connected()}
    assert set(by_name) == {"eDP-1", "DP-1", "DP-2"}
    assert (by_name["DP-1"].x, by_name["DP-1"].y) == (0, 0)
    assert (by_name["DP-2"].x, by_name["DP-2"].y) == (2560, 0)
    assert (by_name["eDP-1"].x, by_name["eDP-1"].y) == (1600, 1440)
    assert by_name["eDP-1"].primary is True
    assert by_name["DP-1"].primary is False


def test_preferred_mode_can_differ_from_current_mode():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    dp2 = next(o for o in state.connected() if o.name == "DP-2")
    assert (dp2.current_mode().width, dp2.current_mode().height) == (2560, 1440)
    assert (dp2.preferred_mode().width, dp2.preferred_mode().height) == (3840, 2160)


def test_edid_differs_per_output():
    text = (FIXTURES / "xrandr_verbose_dual_office.txt").read_text()
    state = parse_verbose(text)
    by_name = {o.name: o.edid for o in state.connected()}
    assert len({by_name["eDP-1"], by_name["DP-1"], by_name["DP-2"]}) == 3


def test_negative_offset_is_parsed_not_dropped_to_zero():
    """A monitor positioned below/left of the origin uses a '-' instead of
    the second '+' in its geometry (e.g. 1920x1080+0-1080). Regression
    test: an earlier version of this regex hard-coded '+' for both
    signs, silently defaulting negative offsets to 0."""
    text = (
        "HDMI-1 connected 1920x1080+0-1080 (0x4a) normal "
        "(normal left inverted right x axis y axis) 520mm x 320mm\n"
        "  1920x1080 (0x4a) 100.00MHz -HSync +VSync *current +preferred\n"
        "        v: height 1080 start 1081 end 1084 total 1118           clock  60.00Hz\n"
    )
    state = parse_verbose(text)
    assert (state.outputs[0].x, state.outputs[0].y) == (0, -1080)


def test_unrecognized_connection_status_does_not_corrupt_the_prior_output():
    """xrandr can report a line like 'DP-5 unknown connection (...)' for
    some outputs. Regression test: an earlier version silently kept
    `current` pointed at the previous output when a header line's status
    didn't match connected|disconnected exactly, so DP-5's property lines
    got misattributed to eDP-1 instead of being cleanly skipped."""
    text = (
        "eDP-1 connected primary 1920x1200+0+0 (0x49) normal "
        "(normal left inverted right x axis y axis) 301mm x 188mm\n"
        "  1920x1200 (0x49) 100.00MHz -HSync -VSync *current +preferred\n"
        "        v: height 1200 start 1203 end 1217 total 1236           clock  60.00Hz\n"
        "DP-5 unknown connection (normal left inverted right x axis y axis)\n"
        "\tCONNECTOR_ID: 999\n"
    )
    state = parse_verbose(text)
    assert [o.name for o in state.outputs] == ["eDP-1", "DP-5"]
    edp1 = state.outputs[0]
    assert len(edp1.modes) == 1
    dp5 = state.outputs[1]
    assert dp5.connected is False


def test_rotation_is_captured_from_the_header_line():
    text = (
        "DP-2 connected 1080x1920+0+0 (0x4b) left "
        "(normal left inverted right x axis y axis) 300mm x 500mm\n"
    )
    state = parse_verbose(text)
    assert state.outputs[0].rotation == "left"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_xrandr_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/xrandr_parser.py
from __future__ import annotations

import re

from bspwm_display_manager.backend.models import LayoutState, Mode, Output

_OUTPUT_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_-]+)\s+"
    r"(?P<status>connected|disconnected|unknown connection)\s*"
    r"(?P<primary>primary\s+)?"
    r"(?:(?P<w>\d+)x(?P<h>\d+)(?P<xoff>[+-]\d+)(?P<yoff>[+-]\d+)\s+)?"
    r"(?:\((?P<modeid>0x[0-9a-fA-F]+)\)\s+(?P<rotation>\S+)\s+\()?"
)
_EDID_HEADER = re.compile(r"^\s*EDID:\s*$")
_EDID_LINE = re.compile(r"^\s{2,}([0-9a-fA-F]+)\s*$")
_MODE_LINE = re.compile(
    r"^\s{2}(?P<w>\d+)x(?P<h>\d+)\s+\((?P<id>0x[0-9a-fA-F]+)\)"
)
_RATE = re.compile(r"clock\s+([\d.]+)Hz")


def parse_verbose(text: str) -> LayoutState:
    outputs: list[Output] = []
    current: Output | None = None
    in_edid = False
    edid_hex: list[str] = []
    pending_mode_header: tuple[int, int, str, bool, bool] | None = None

    def flush_edid():
        nonlocal in_edid, edid_hex
        if current is not None and edid_hex:
            current.edid = "".join(edid_hex)
        in_edid = False
        edid_hex = []

    for line in text.splitlines():
        m = _OUTPUT_LINE.match(line)
        if m:
            flush_edid()
            pending_mode_header = None
            connected = m.group("status") == "connected"
            # int() accepts a leading '+' or '-', so the signed xoff/yoff
            # groups (not a hard-coded '+') give correct negative offsets
            # for monitors positioned below/left of the origin.
            x = int(m.group("xoff")) if m.group("xoff") else 0
            y = int(m.group("yoff")) if m.group("yoff") else 0
            rotation = m.group("rotation") if m.group("rotation") else "normal"
            current = Output(
                name=m.group("name"),
                connected=connected,
                primary=bool(m.group("primary")),
                edid=None,
                x=x,
                y=y,
                rotation=rotation,
                scale_x=1.0,
                scale_y=1.0,
                modes=[],
            )
            outputs.append(current)
            continue

        if current is None:
            continue

        if _EDID_HEADER.match(line):
            in_edid = True
            edid_hex = []
            continue
        if in_edid:
            hexm = _EDID_LINE.match(line)
            if hexm:
                edid_hex.append(hexm.group(1))
                continue
            else:
                flush_edid()

        mode_m = _MODE_LINE.match(line)
        if mode_m:
            pending_mode_header = (
                int(mode_m.group("w")),
                int(mode_m.group("h")),
                mode_m.group("id"),
                "*current" in line,
                "+preferred" in line,
            )
            continue

        rate_m = _RATE.search(line)
        if rate_m and pending_mode_header is not None:
            w, h, mid, is_current, is_preferred = pending_mode_header
            mode = Mode(
                width=w, height=h, rate=float(rate_m.group(1)), id=mid,
                current=is_current, preferred=is_preferred,
            )
            current.modes.append(mode)
            pending_mode_header = None

    flush_edid()
    return LayoutState(outputs=outputs)
```

Every output-header-shaped line — including one whose status is neither
`connected` nor `disconnected` (xrandr's `unknown connection`) — matches
`_OUTPUT_LINE` and reassigns `current`, `pending_mode_header` resets at
every such boundary too. This is deliberate: it's what stops an
unrecognized or unusual header line from leaving `current` pointed at
the *previous* output, which would otherwise misattribute that output's
property/mode/EDID lines to the wrong monitor.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_xrandr_parser.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/xrandr_parser.py tests/backend/test_xrandr_parser.py tests/fixtures
git commit -m "$(cat <<'EOF'
Parse xrandr --verbose into LayoutState

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 4: xrandr subprocess client

**Files:**
- Create: `src/bspwm_display_manager/backend/xrandr_client.py`
- Test: `tests/backend/test_xrandr_client.py`

**Interfaces:**
- Produces:
  - `query_verbose() -> str` (runs `xrandr --verbose`, returns stdout)
  - `apply(args: list[str]) -> ApplyResult`
  - `ApplyResult(ok: bool, returncode: int, stderr: str)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_xrandr_client.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_xrandr_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/xrandr_client.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class ApplyResult:
    ok: bool
    returncode: int
    stderr: str


def query_verbose() -> str:
    result = subprocess.run(
        ["xrandr", "--verbose"], capture_output=True, text=True, check=False
    )
    return result.stdout


def apply(args: list[str]) -> ApplyResult:
    result = subprocess.run(
        ["xrandr", *args], capture_output=True, text=True, check=False
    )
    return ApplyResult(ok=result.returncode == 0, returncode=result.returncode, stderr=result.stderr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_xrandr_client.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/xrandr_client.py tests/backend/test_xrandr_client.py
git commit -m "$(cat <<'EOF'
Add xrandr subprocess client (query + apply)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 5: Command builder (xrandr args + scale env)

**Files:**
- Create: `src/bspwm_display_manager/backend/command_builder.py`
- Test: `tests/backend/test_command_builder.py`

**Interfaces:**
- Consumes: `Output`, `LayoutState` from Task 2.
- Produces:
  - `build_xrandr_args(outputs: list[Output]) -> list[str]`
  - `build_scale_env(percent: int) -> dict[str, str]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_command_builder.py
from bspwm_display_manager.backend.command_builder import build_scale_env, build_xrandr_args
from bspwm_display_manager.backend.models import Mode, Output


def _output(name, w, h, rate, x, y, primary=False, off=False, scale=(1.0, 1.0)):
    modes = [] if off else [Mode(width=w, height=h, rate=rate, id="0x1", current=True, preferred=True)]
    return Output(name=name, connected=not off, primary=primary, edid="e",
                  x=x, y=y, rotation="normal", scale_x=scale[0], scale_y=scale[1], modes=modes)


def test_builds_one_output_clause_per_output_in_order():
    outs = [
        _output("DP-1", 2560, 1440, 59.95, 0, 0),
        _output("eDP-1", 1920, 1200, 60.03, 1600, 1440, primary=True),
    ]
    args = build_xrandr_args(outs)
    assert args == [
        "--output", "DP-1", "--mode", "2560x1440", "--rate", "59.95",
        "--pos", "0x0", "--rotate", "normal",
        "--output", "eDP-1", "--mode", "1920x1200", "--rate", "60.03",
        "--pos", "1600x1440", "--rotate", "normal", "--primary",
    ]


def test_off_output_only_gets_output_and_off():
    outs = [_output("HDMI-1", 0, 0, 0, 0, 0, off=True)]
    args = build_xrandr_args(outs)
    assert args == ["--output", "HDMI-1", "--off"]


def test_non_default_scale_adds_scale_flag():
    outs = [_output("DP-2", 3840, 2160, 59.98, 0, 0, scale=(0.5, 0.5))]
    args = build_xrandr_args(outs)
    assert args == [
        "--output", "DP-2", "--mode", "3840x2160", "--rate", "59.98",
        "--pos", "0x0", "--rotate", "normal", "--scale", "0.5x0.5",
    ]


def test_build_scale_env_100_percent_is_baseline_dpi():
    env = build_scale_env(100)
    assert env["GDK_SCALE"] == "1"
    assert env["QT_SCALE_FACTOR"] == "1"
    assert env["QT_AUTO_SCREEN_SCALE_FACTOR"] == "0"
    assert env["Xft.dpi"] == "96"


def test_build_scale_env_150_percent():
    env = build_scale_env(150)
    assert env["GDK_SCALE"] == "1.5"
    assert env["QT_SCALE_FACTOR"] == "1.5"
    assert env["Xft.dpi"] == "144"


def test_build_scale_env_rounds_rather_than_truncates_non_quarter_percentages():
    """110% -> 96*1.1 = 105.6. int() truncates to 105 (silently 1 dpi
    low); the correct, non-biased value is round() -> 106. Only
    percentages that are multiples of 25 land on an exact integer, so
    this regression would not be caught by the 100%/150% tests above."""
    env = build_scale_env(110)
    assert env["Xft.dpi"] == "106"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_command_builder.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/command_builder.py
from __future__ import annotations

from bspwm_display_manager.backend.models import Output

_BASE_DPI = 96


def build_xrandr_args(outputs: list[Output]) -> list[str]:
    args: list[str] = []
    for out in outputs:
        args += ["--output", out.name]
        mode = out.current_mode()
        if mode is None:
            args += ["--off"]
            continue
        args += [
            "--mode", f"{mode.width}x{mode.height}",
            "--rate", f"{mode.rate}",
            "--pos", f"{out.x}x{out.y}",
            "--rotate", out.rotation,
        ]
        if out.primary:
            args += ["--primary"]
        if (out.scale_x, out.scale_y) != (1.0, 1.0):
            args += ["--scale", f"{out.scale_x}x{out.scale_y}"]
    return args


def build_scale_env(percent: int) -> dict[str, str]:
    factor = percent / 100
    return {
        "GDK_SCALE": _trim(factor),
        "QT_SCALE_FACTOR": _trim(factor),
        "QT_AUTO_SCREEN_SCALE_FACTOR": "0",
        "Xft.dpi": str(round(_BASE_DPI * factor)),
    }


def _trim(value: float) -> str:
    return f"{value:g}"
```

Note: `test_off_output_only_gets_output_and_off` requires primary/scale to
not apply to an off output — the implementation's early `continue` for
`mode is None` already guarantees that.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_command_builder.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/command_builder.py tests/backend/test_command_builder.py
git commit -m "$(cat <<'EOF'
Add xrandr arg builder and scale env builder

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 6: EDID fingerprint and scale suggestion

**Files:**
- Create: `src/bspwm_display_manager/backend/edid.py`
- Create: `src/bspwm_display_manager/backend/scale.py`
- Test: `tests/backend/test_edid.py`
- Test: `tests/backend/test_scale.py`

**Interfaces:**
- Consumes: `Output` from Task 2.
- Produces:
  - `fingerprint(outputs: list[Output]) -> str`
  - `suggest_global_scale(outputs: list[Output]) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_edid.py
from bspwm_display_manager.backend.edid import fingerprint
from bspwm_display_manager.backend.models import Output


def _o(name, edid):
    return Output(name=name, connected=True, primary=False, edid=edid,
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[])


def test_fingerprint_is_stable_regardless_of_input_order():
    a = [_o("DP-1", "aaa"), _o("DP-2", "bbb")]
    b = [_o("DP-2", "bbb"), _o("DP-1", "aaa")]
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_is_stable_regardless_of_port_name():
    a = [_o("DP-1", "aaa"), _o("DP-2", "bbb")]
    b = [_o("HDMI-1", "aaa"), _o("DP-9", "bbb")]
    assert fingerprint(a) == fingerprint(b)


def test_fingerprint_differs_for_different_monitor_sets():
    a = [_o("DP-1", "aaa")]
    b = [_o("DP-1", "ccc")]
    assert fingerprint(a) != fingerprint(b)


def test_fingerprint_ignores_outputs_with_no_edid():
    a = [_o("DP-1", "aaa"), _o("VIRTUAL-1", None)]
    b = [_o("DP-1", "aaa")]
    assert fingerprint(a) == fingerprint(b)
```

```python
# tests/backend/test_scale.py
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.backend.scale import suggest_global_scale


def _o(name, w, h):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_suggests_150_percent_for_clean_1point5x_pair():
    outs = [_o("DP-1", 2560, 1440), _o("DP-2", 3840, 2160)]
    assert suggest_global_scale(outs) == 150


def test_suggests_100_percent_for_matching_resolutions():
    outs = [_o("DP-1", 1920, 1080), _o("DP-2", 1920, 1080)]
    assert suggest_global_scale(outs) == 100


def test_suggests_100_percent_for_a_single_output():
    outs = [_o("eDP-1", 1920, 1200)]
    assert suggest_global_scale(outs) == 100


def test_falls_back_to_100_for_a_non_clean_ratio():
    outs = [_o("DP-1", 1920, 1080), _o("DP-2", 2560, 1440)]
    assert suggest_global_scale(outs) == 100


def test_three_outputs_where_every_height_fits_one_of_two_clean_tiers():
    """Two matching 1440p monitors plus one 4K: every height is either
    at the 1x tier (1440) or the 1.5x tier (2160), so a single global
    scale keeps every screen consistently sized."""
    outs = [_o("DP-1", 2560, 1440), _o("DP-2", 2560, 1440), _o("DP-3", 3840, 2160)]
    assert suggest_global_scale(outs) == 150


def test_three_outputs_with_a_height_that_fits_neither_tier_falls_back_to_100():
    """Regression test: an earlier version of this function only ever
    checked the tallest/shortest pair, so three outputs at heights
    1000/1300/1500 wrongly returned 150 (matching the 1000:1500 = 1.5
    extremes) while silently ignoring that 1300 fits neither the 1x nor
    the 1.5x tier -- that output would not actually be consistently
    sized under the suggested scale."""
    outs = [_o("DP-1", 1000, 1000), _o("DP-2", 1300, 1300), _o("DP-3", 1500, 1500)]
    assert suggest_global_scale(outs) == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_edid.py tests/backend/test_scale.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/edid.py
from __future__ import annotations

import hashlib

from bspwm_display_manager.backend.models import Output


def fingerprint(outputs: list[Output]) -> str:
    edids = sorted(o.edid for o in outputs if o.edid)
    joined = "|".join(edids)
    return hashlib.sha256(joined.encode()).hexdigest()
```

```python
# src/bspwm_display_manager/backend/scale.py
from __future__ import annotations

from bspwm_display_manager.backend.models import Output

# Ratios clean enough that the global-DPI route renders crisply on every
# connected output at once (see the design spec's "Platform constraints"
# section) mapped to the suggested whole-desktop scale percentage.
_CLEAN_RATIOS = {1.0: 100, 1.25: 125, 1.5: 150, 1.75: 175, 2.0: 200}
_TOLERANCE = 0.02


def suggest_global_scale(outputs: list[Output]) -> int:
    heights = []
    for out in outputs:
        mode = out.current_mode() or out.preferred_mode()
        if mode is not None:
            heights.append(mode.height)
    if len(heights) < 2:
        return 100

    tallest, shortest = max(heights), min(heights)
    if shortest == 0:
        return 100
    ratio = tallest / shortest
    for clean_ratio, percent in _CLEAN_RATIOS.items():
        if abs(ratio - clean_ratio) > _TOLERANCE:
            continue
        # The tallest/shortest pair alone isn't enough with 3+ outputs:
        # a middle-sized monitor could fit neither the "1x" tier (the
        # shortest) nor the "clean_ratio x" tier (the tallest), meaning
        # it would NOT be consistently sized under this suggested scale
        # even though the pair looks clean. Every connected output must
        # land near one of the two tiers before this ratio counts.
        tiers = (1.0, clean_ratio)
        if all(
            any(abs(h / shortest - tier) <= _TOLERANCE for tier in tiers)
            for h in heights
        ):
            return percent
    return 100
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_edid.py tests/backend/test_scale.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/edid.py src/bspwm_display_manager/backend/scale.py tests/backend/test_edid.py tests/backend/test_scale.py
git commit -m "$(cat <<'EOF'
Add EDID fingerprinting and global scale suggestion

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 7: Profile model and store

**Files:**
- Create: `src/bspwm_display_manager/backend/profile.py`
- Create: `src/bspwm_display_manager/backend/profile_store.py`
- Test: `tests/backend/test_profile.py`
- Test: `tests/backend/test_profile_store.py`

**Interfaces:**
- Consumes: nothing beyond the standard library (profile is a
  serialization-only model; fingerprint/scale are computed by callers
  and passed in, keeping this module free of RandR/EDID logic).
- Produces:
  - `OutputSpec(edid_or_pattern: str, mode: tuple[int, int], rate: float, x: int, y: int, rotation: str, scale_x: float, scale_y: float, primary: bool)`
  - `Profile(name: str, fingerprint: str, scale_percent: int, outputs: list[OutputSpec], desktop_assignment: dict[str, list[str]], hooks: list[str])`
    - `Profile.to_dict() -> dict`
    - `Profile.from_dict(data: dict) -> Profile` (classmethod)
  - `save(profile: Profile, config_dir: Path) -> None`
  - `load(name: str, config_dir: Path) -> Profile`
  - `list_profiles(config_dir: Path) -> list[str]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_profile.py
from bspwm_display_manager.backend.profile import OutputSpec, Profile


def _sample_profile():
    return Profile(
        name="work",
        fingerprint="abc123",
        scale_percent=150,
        outputs=[
            OutputSpec(edid_or_pattern="edid-dell", mode=(2560, 1440), rate=59.95,
                       x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=False),
            OutputSpec(edid_or_pattern="eDP-*", mode=(1920, 1200), rate=60.03,
                       x=1600, y=1440, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True),
        ],
        desktop_assignment={"eDP-*": ["term", "chat", "media"], "edid-dell": ["pm", "office", "settings"]},
        hooks=["setsid -f bspbar"],
    )


def test_profile_round_trips_through_dict():
    profile = _sample_profile()
    restored = Profile.from_dict(profile.to_dict())
    assert restored == profile


def test_output_spec_round_trips_mode_as_a_list_in_json_safe_dict():
    profile = _sample_profile()
    d = profile.to_dict()
    assert d["outputs"][0]["mode"] == [2560, 1440]
```

```python
# tests/backend/test_profile_store.py
import pytest

from bspwm_display_manager.backend.profile import OutputSpec, Profile
from bspwm_display_manager.backend.profile_store import list_profiles, load, save


def _sample_profile(name="work"):
    return Profile(
        name=name, fingerprint="fp1", scale_percent=100,
        outputs=[OutputSpec(edid_or_pattern="eDP-*", mode=(1920, 1200), rate=60.03,
                             x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, primary=True)],
        desktop_assignment={"eDP-*": ["term"]},
        hooks=[],
    )


def test_save_then_load_round_trips(tmp_path):
    profile = _sample_profile()
    save(profile, tmp_path)
    loaded = load("work", tmp_path)
    assert loaded == profile


def test_load_missing_profile_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load("nonexistent", tmp_path)


def test_list_profiles_returns_names_sorted(tmp_path):
    save(_sample_profile("work"), tmp_path)
    save(_sample_profile("home"), tmp_path)
    assert list_profiles(tmp_path) == ["home", "work"]


def test_list_profiles_empty_dir_returns_empty_list(tmp_path):
    assert list_profiles(tmp_path) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_profile.py tests/backend/test_profile_store.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/profile.py
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OutputSpec:
    edid_or_pattern: str
    mode: tuple[int, int]
    rate: float
    x: int
    y: int
    rotation: str
    scale_x: float
    scale_y: float
    primary: bool

    def to_dict(self) -> dict:
        return {
            "edid_or_pattern": self.edid_or_pattern,
            "mode": list(self.mode),
            "rate": self.rate,
            "x": self.x, "y": self.y,
            "rotation": self.rotation,
            "scale_x": self.scale_x, "scale_y": self.scale_y,
            "primary": self.primary,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "OutputSpec":
        return cls(
            edid_or_pattern=d["edid_or_pattern"],
            mode=tuple(d["mode"]),
            rate=d["rate"], x=d["x"], y=d["y"], rotation=d["rotation"],
            scale_x=d["scale_x"], scale_y=d["scale_y"], primary=d["primary"],
        )


@dataclass
class Profile:
    name: str
    fingerprint: str
    scale_percent: int
    outputs: list[OutputSpec] = field(default_factory=list)
    desktop_assignment: dict[str, list[str]] = field(default_factory=dict)
    hooks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "fingerprint": self.fingerprint,
            "scale_percent": self.scale_percent,
            "outputs": [o.to_dict() for o in self.outputs],
            "desktop_assignment": self.desktop_assignment,
            "hooks": self.hooks,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Profile":
        return cls(
            name=d["name"],
            fingerprint=d["fingerprint"],
            scale_percent=d["scale_percent"],
            outputs=[OutputSpec.from_dict(o) for o in d["outputs"]],
            desktop_assignment=d["desktop_assignment"],
            hooks=d["hooks"],
        )
```

```python
# src/bspwm_display_manager/backend/profile_store.py
from __future__ import annotations

import json
from pathlib import Path

from bspwm_display_manager.backend.profile import Profile


def _path(name: str, config_dir: Path) -> Path:
    return config_dir / f"{name}.json"


def save(profile: Profile, config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    _path(profile.name, config_dir).write_text(json.dumps(profile.to_dict(), indent=2))


def load(name: str, config_dir: Path) -> Profile:
    path = _path(name, config_dir)
    if not path.exists():
        raise FileNotFoundError(f"no profile named {name!r} in {config_dir}")
    return Profile.from_dict(json.loads(path.read_text()))


def list_profiles(config_dir: Path) -> list[str]:
    if not config_dir.exists():
        return []
    return sorted(p.stem for p in config_dir.glob("*.json"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_profile.py tests/backend/test_profile_store.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/profile.py src/bspwm_display_manager/backend/profile_store.py tests/backend/test_profile.py tests/backend/test_profile_store.py
git commit -m "$(cat <<'EOF'
Add Profile model and JSON profile store

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 8: bspc subprocess client

**Files:**
- Create: `src/bspwm_display_manager/backend/bspc_client.py`
- Test: `tests/backend/test_bspc_client.py`

**Interfaces:**
- Produces (each a thin one-call subprocess wrapper around `bspc`):
  - `query_monitor_names() -> list[str]`
  - `query_desktop_names(monitor: str | None = None) -> list[str]`
  - `desktop_exists(name: str) -> bool`
  - `move_desktop_to_monitor(desktop: str, target: str) -> None`
  - `add_desktop(monitor: str, name: str) -> None`
  - `remove_desktop(name: str) -> None`
  - `remove_monitor(name: str) -> None`
  - `reset_padding(monitor: str) -> None`
  - `reorder_monitors(order: list[str]) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_bspc_client.py
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


def test_move_desktop_to_monitor():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.move_desktop_to_monitor("pm", "DP-1")
    run.assert_called_once_with(
        ["bspc", "desktop", "pm", "--to-monitor", "DP-1"], capture_output=True, text=True, check=False
    )


def test_add_desktop():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.add_desktop("DP-1", "pm")
    run.assert_called_once_with(
        ["bspc", "monitor", "DP-1", "-a", "pm"], capture_output=True, text=True, check=False
    )


def test_remove_desktop():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.remove_desktop("ghost")
    run.assert_called_once_with(
        ["bspc", "desktop", "ghost", "-r"], capture_output=True, text=True, check=False
    )


def test_remove_monitor():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.remove_monitor("HDMI-1")
    run.assert_called_once_with(
        ["bspc", "monitor", "HDMI-1", "-r"], capture_output=True, text=True, check=False
    )


def test_reset_padding_sets_all_four_edges_to_zero():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.reset_padding("eDP-1")
    assert run.call_count == 4
    calls = [c.args[0] for c in run.call_args_list]
    for edge in ("top_padding", "bottom_padding", "left_padding", "right_padding"):
        assert ["bspc", "config", "-m", "eDP-1", edge, "0"] in calls


def test_reorder_monitors():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake) as run:
        bc.reorder_monitors(["DP-1", "eDP-1", "DP-2"])
    run.assert_called_once_with(
        ["bspc", "wm", "-O", "DP-1", "eDP-1", "DP-2"], capture_output=True, text=True, check=False
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_bspc_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/bspc_client.py
from __future__ import annotations

import subprocess

_PADDING_EDGES = ("top_padding", "bottom_padding", "left_padding", "right_padding")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["bspc", *args], capture_output=True, text=True, check=False)


def query_monitor_names() -> list[str]:
    result = _run(["query", "-M", "--names"])
    return [l for l in result.stdout.splitlines() if l]


def query_desktop_names(monitor: str | None = None) -> list[str]:
    args = ["query", "-D"]
    if monitor is not None:
        args += ["-m", monitor]
    args += ["--names"]
    result = _run(args)
    return [l for l in result.stdout.splitlines() if l]


def desktop_exists(name: str) -> bool:
    return _run(["query", "-D", "-d", name]).returncode == 0


def move_desktop_to_monitor(desktop: str, target: str) -> None:
    _run(["desktop", desktop, "--to-monitor", target])


def add_desktop(monitor: str, name: str) -> None:
    _run(["monitor", monitor, "-a", name])


def remove_desktop(name: str) -> None:
    _run(["desktop", name, "-r"])


def remove_monitor(name: str) -> None:
    _run(["monitor", name, "-r"])


def reset_padding(monitor: str) -> None:
    for edge in _PADDING_EDGES:
        _run(["config", "-m", monitor, edge, "0"])


def reorder_monitors(order: list[str]) -> None:
    _run(["wm", "-O", *order])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_bspc_client.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/bspc_client.py tests/backend/test_bspc_client.py
git commit -m "$(cat <<'EOF'
Add thin bspc subprocess client

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 9: Desktop Reconciliation (the ported prior-art logic)

This is the highest-risk task in the plan — it ports every hard-won
behavior from the spec's "Prior art" section. Read that section again
before implementing.

**Files:**
- Modify: `src/bspwm_display_manager/backend/bspc_client.py` (add
  `desktop_is_empty`)
- Modify: `tests/backend/test_bspc_client.py` (add its test)
- Create: `src/bspwm_display_manager/backend/reconcile.py`
- Test: `tests/backend/test_reconcile.py`

**Interfaces:**
- Consumes: every function in `bspc_client` from Task 8, plus the new
  `desktop_is_empty`, plus Task 8's six mutating functions
  (`move_desktop_to_monitor`, `add_desktop`, `remove_desktop`,
  `remove_monitor`, `reset_padding`, `reorder_monitors`) — this task
  changes their return type from `None` to `bool` (see Step 1b) so this
  layer has a failure signal to act on, per the design spec's error
  handling section ("surfaces the error rather than silently continuing
  to the next step").
- Produces:
  - `ReconciliationError(RuntimeError)` — raised immediately when any
    underlying `bspc` call fails, rather than continuing past it.
  - `retire_monitors(overflow_target: str, survivors: list[str]) -> None`
  - `assign_desktops(target: str, names: list[str]) -> None`
  - `sweep_placeholder_desktops(expected_names: set[str]) -> None`
  - `reset_active_padding(active_monitors: list[str]) -> None`
  - `reconcile(active_monitors: list[str], desktop_assignment: dict[str, list[str]], order: list[str]) -> None`
    (runs padding reset, assignment, reorder, and the placeholder sweep,
    in that order — everything from spec step 3 onward; `retire_monitors`
    is deliberately NOT called from inside `reconcile`, since it must run
    *before* the `xrandr` apply, not after — Task 11 calls it separately)

- [ ] **Step 1: Add the `desktop_is_empty` test to `test_bspc_client.py`**

```python
# appended to tests/backend/test_bspc_client.py
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
```

- [ ] **Step 1b: Update `test_bspc_client.py`'s existing mutating-function tests to also assert the new `bool` return value**

Task 8 built these six functions to return `None`, matching the exact
tests written then. This step changes that: each mutating function now
returns whether its `bspc` call succeeded, so `reconcile.py` has
something to check. Edit each existing test below (they already exist in
`tests/backend/test_bspc_client.py` from Task 8) to add a success-path
return-value assertion, and add one new failure-path test per function:

```python
# tests/backend/test_bspc_client.py — edit these EXISTING tests (from
# Task 8) to add the marked assertion line, and add the new tests below
# them. Everything else in each existing test (the fake, the patch, the
# run.assert_called_once_with(...)) stays exactly as Task 8 wrote it.

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
```

- [ ] **Step 2: Add `desktop_is_empty` to `bspc_client.py`, and change the six mutating functions to return `bool`**

```python
# appended to src/bspwm_display_manager/backend/bspc_client.py
def desktop_is_empty(name: str) -> bool:
    result = _run(["query", "-N", "-d", name, "-n", ".window"])
    return result.stdout.strip() == ""
```

```python
# REPLACE these six existing functions in
# src/bspwm_display_manager/backend/bspc_client.py (from Task 8) with
# these versions — same argv construction, now returning bool:

def move_desktop_to_monitor(desktop: str, target: str) -> bool:
    return _run(["desktop", desktop, "--to-monitor", target]).returncode == 0


def add_desktop(monitor: str, name: str) -> bool:
    return _run(["monitor", monitor, "-a", name]).returncode == 0


def remove_desktop(name: str) -> bool:
    return _run(["desktop", name, "-r"]).returncode == 0


def remove_monitor(name: str) -> bool:
    return _run(["monitor", name, "-r"]).returncode == 0


def reset_padding(monitor: str) -> bool:
    ok = True
    for edge in _PADDING_EDGES:
        if _run(["config", "-m", monitor, edge, "0"]).returncode != 0:
            ok = False
    return ok


def reorder_monitors(order: list[str]) -> bool:
    return _run(["wm", "-O", *order]).returncode == 0
```

- [ ] **Step 3: Run to verify the updated/new bspc_client tests pass**

Run: `.venv/bin/pytest tests/backend/test_bspc_client.py -v`
Expected: 19 passed

- [ ] **Step 4: Commit the bspc_client addition**

```bash
git add src/bspwm_display_manager/backend/bspc_client.py tests/backend/test_bspc_client.py
git commit -m "$(cat <<'EOF'
Add bspc_client.desktop_is_empty; mutating functions now return bool

The six mutating functions (move_desktop_to_monitor, add_desktop,
remove_desktop, remove_monitor, reset_padding, reorder_monitors)
previously discarded bspc's exit code entirely. reconcile.py (next in
this task) needs a failure signal to fulfil the design spec's error
handling requirement ("surfaces the error rather than silently
continuing to the next step").

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

- [ ] **Step 5: Write the failing reconcile tests**

```python
# tests/backend/test_reconcile.py
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
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_reconcile.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 7: Write the implementation**

```python
# src/bspwm_display_manager/backend/reconcile.py
from __future__ import annotations

from bspwm_display_manager.backend import bspc_client

_PLACEHOLDER = "__bsp_retiring__"


class ReconciliationError(RuntimeError):
    """A bspc call failed. Retirement and assignment are both idempotent
    by construction, so the caller can safely retry the whole operation
    rather than trying to resume mid-way."""


def retire_monitors(overflow_target: str, survivors: list[str]) -> None:
    """Move every desktop off any monitor not in `survivors`, then
    remove that monitor. MUST be called before the xrandr command that
    disables/reconfigures the losing output — bspc_client.remove_monitor
    drops (does not merge) a monitor's windows the instant it runs."""
    keep = set(survivors) | {overflow_target}
    for mon in bspc_client.query_monitor_names():
        if mon in keep:
            continue
        # A monitor can never have zero desktops, so bspc refuses to move
        # its last one — add a disposable placeholder first so no real
        # desktop is ever "the last one" while being moved off.
        if not bspc_client.add_desktop(mon, _PLACEHOLDER):
            raise ReconciliationError(f"failed to add placeholder desktop on {mon!r}")
        for desk in bspc_client.query_desktop_names(monitor=mon):
            if desk == _PLACEHOLDER:
                continue
            if not bspc_client.move_desktop_to_monitor(desk, overflow_target):
                raise ReconciliationError(f"failed to move desktop {desk!r} off {mon!r}")
        if not bspc_client.remove_monitor(mon):
            raise ReconciliationError(f"failed to remove monitor {mon!r}")


def assign_desktops(target: str, names: list[str]) -> None:
    """Move each named desktop to `target` by identity if it exists
    anywhere, else create it fresh. Never uses `bspc monitor -d`, which
    silently folds a shrinking desktop list's dropped names into the
    last name in the new list instead of releasing them elsewhere."""
    for name in names:
        if bspc_client.desktop_exists(name):
            if not bspc_client.move_desktop_to_monitor(name, target):
                raise ReconciliationError(f"failed to move desktop {name!r} to {target!r}")
        else:
            if not bspc_client.add_desktop(target, name):
                raise ReconciliationError(f"failed to add desktop {name!r} on {target!r}")


def sweep_placeholder_desktops(expected_names: set[str]) -> None:
    """Remove any desktop not in `expected_names` (e.g. bspwm's
    auto-created blank desktop on a newly-appeared monitor), but only if
    it holds no windows, so nothing unexpected is silently destroyed."""
    for name in bspc_client.query_desktop_names():
        if name in expected_names:
            continue
        if bspc_client.desktop_is_empty(name):
            if not bspc_client.remove_desktop(name):
                raise ReconciliationError(f"failed to remove stray desktop {name!r}")


def reset_active_padding(active_monitors: list[str]) -> None:
    for mon in active_monitors:
        if not bspc_client.reset_padding(mon):
            raise ReconciliationError(f"failed to reset padding on {mon!r}")


def reconcile(
    active_monitors: list[str],
    desktop_assignment: dict[str, list[str]],
    order: list[str],
) -> None:
    """Everything that happens after a successful xrandr apply. Does NOT
    call retire_monitors — that must run before the xrandr apply, so the
    caller (backend.apply) is responsible for sequencing it separately."""
    reset_active_padding(active_monitors)
    for target, names in desktop_assignment.items():
        assign_desktops(target, names)
    if not bspc_client.reorder_monitors(order):
        raise ReconciliationError(f"failed to reorder monitors: {order!r}")
    expected = {name for names in desktop_assignment.values() for name in names}
    sweep_placeholder_desktops(expected)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_reconcile.py -v`
Expected: 13 passed

- [ ] **Step 9: Commit**

```bash
git add src/bspwm_display_manager/backend/reconcile.py tests/backend/test_reconcile.py
git commit -m "$(cat <<'EOF'
Port desktop reconciliation from bsp-assign-desktops/bsp-retire-monitors

Generalizes the hard-won bspc edge cases documented in the design spec's
Prior Art section: the last-desktop placeholder-move workaround, never
using bspc monitor -d to reassign desktops (it folds dropped names into
the last one instead of releasing them), and the empty-only placeholder
desktop sweep. Every bspc_client call is checked and raises
ReconciliationError immediately on failure rather than continuing past
it, per the design spec's error handling section.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 10: Post-apply hooks runner

**Files:**
- Create: `src/bspwm_display_manager/backend/hooks.py`
- Test: `tests/backend/test_hooks.py`

**Interfaces:**
- Produces: `run_hooks(commands: list[str]) -> list[HookResult]`,
  `HookResult(command: str, ok: bool, stderr: str)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_hooks.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_hooks.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/hooks.py
from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass
class HookResult:
    command: str
    ok: bool
    stderr: str


def run_hooks(commands: list[str]) -> list[HookResult]:
    results = []
    for command in commands:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, check=False)
        results.append(HookResult(command=command, ok=result.returncode == 0, stderr=result.stderr))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_hooks.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/backend/hooks.py tests/backend/test_hooks.py
git commit -m "$(cat <<'EOF'
Add post-apply hook runner

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 11: Apply orchestration

**Files:**
- Create: `src/bspwm_display_manager/backend/apply.py`
- Test: `tests/backend/test_apply.py`

**Interfaces:**
- Consumes: `Profile`/`OutputSpec` (Task 7), `LayoutState`/`Output`/`Mode`
  (Task 2), `xrandr_parser.parse_verbose` (Task 3), `xrandr_client`
  (Task 4), `command_builder` (Task 5), `reconcile` (Task 9), `hooks`
  (Task 10).
- Produces:
  - `ApplyOutcome(ok: bool, message: str)`
  - `resolve_targets(profile: Profile, state: LayoutState) -> dict[str, str]`
    (maps each `OutputSpec.edid_or_pattern` to the real connected
    output name it matches — exact EDID match first, else glob pattern
    match against the output name, e.g. `eDP-*`)
  - `apply_geometry(outputs: list[Output], overflow_target: str, survivors: list[str]) -> ApplyOutcome`
    (retire, then xrandr apply — this is the GUI's pre-confirm step;
    catches Task 9's `reconcile.ReconciliationError` from `retire_monitors`
    AND `OSError` from `xrandr_client.apply` — e.g. the `xrandr` binary
    itself missing — reporting either as `ApplyOutcome(ok=False, ...)`
    rather than raising, since `ApplyOutcome` is the whole contract
    Task 18's GUI gates on)
  - `finish_reconciliation(profile: Profile, resolved: dict[str, str], order: list[str]) -> ApplyOutcome`
    (scale env, desktop reconciliation, hooks — this is the GUI's
    post-confirm step; catches `reconcile.ReconciliationError` from
    `reconcile.reconcile` AND `OSError` from `apply_scale_env` the same
    way)
  - `replay_profile(profile: Profile) -> ApplyOutcome` (the full
    non-interactive CLI/daemon path: resolve → apply_geometry →
    finish_reconciliation — returns whichever `ApplyOutcome` reflects the
    actual failure point, so callers never need to know about
    `ReconciliationError` at all)

- [ ] **Step 1: Write the failing tests**

```python
# tests/backend/test_apply.py
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


def test_apply_scale_env_writes_env_file_and_merges_xft_dpi_via_xrdb(tmp_path, monkeypatch):
    """The only test that actually exercises apply_scale_env's body —
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/backend/test_apply.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/backend/apply.py
from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass
from pathlib import Path

from bspwm_display_manager.backend import bspc_client, command_builder, hooks, reconcile
from bspwm_display_manager.backend import xrandr_client, xrandr_parser
from bspwm_display_manager.backend.models import LayoutState, Mode, Output
from bspwm_display_manager.backend.profile import Profile


@dataclass
class ApplyOutcome:
    ok: bool
    message: str


def resolve_targets(profile: Profile, state: LayoutState) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for spec in profile.outputs:
        match = None
        for out in state.connected():
            if out.edid == spec.edid_or_pattern or fnmatch.fnmatch(out.name, spec.edid_or_pattern):
                match = out.name
                break
        if match is None:
            raise ValueError(f"no connected output matches {spec.edid_or_pattern!r}")
        resolved[spec.edid_or_pattern] = match
    return resolved


def _outputs_for_apply(profile: Profile, resolved: dict[str, str]) -> list[Output]:
    outputs = []
    for spec in profile.outputs:
        mode = Mode(width=spec.mode[0], height=spec.mode[1], rate=spec.rate,
                     id="", current=True, preferred=False)
        outputs.append(Output(
            name=resolved[spec.edid_or_pattern], connected=True, primary=spec.primary,
            edid=None, x=spec.x, y=spec.y, rotation=spec.rotation,
            scale_x=spec.scale_x, scale_y=spec.scale_y, modes=[mode],
        ))
    return outputs


def apply_geometry(outputs: list[Output], overflow_target: str, survivors: list[str]) -> ApplyOutcome:
    try:
        reconcile.retire_monitors(overflow_target=overflow_target, survivors=survivors)
    except reconcile.ReconciliationError as exc:
        return ApplyOutcome(ok=False, message=str(exc))
    args = command_builder.build_xrandr_args(outputs)
    try:
        result = xrandr_client.apply(args)
    except OSError as exc:
        # e.g. the xrandr binary itself is missing -- ApplyOutcome is the
        # whole contract Task 18's GUI gates on, so this must not escape
        # as a raw exception any more than ReconciliationError may.
        return ApplyOutcome(ok=False, message=str(exc))
    return ApplyOutcome(ok=result.ok, message=result.stderr)


def apply_scale_env(percent: int) -> None:
    env = command_builder.build_scale_env(percent)
    subprocess.run(["xrdb", "-merge"], input=f"Xft.dpi: {env['Xft.dpi']}\n",
                    text=True, check=False)
    env_path = Path.home() / ".config" / "bspwm-display-manager" / "env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"export {k}={v}\n" for k, v in env.items() if k != "Xft.dpi"]
    env_path.write_text("".join(lines))


def finish_reconciliation(profile: Profile, resolved: dict[str, str], order: list[str]) -> ApplyOutcome:
    try:
        apply_scale_env(profile.scale_percent)
    except OSError as exc:
        # apply_scale_env writes a real file and shells out to xrdb --
        # both can raise (permission denied, xrdb missing). Same
        # never-raise contract as the ReconciliationError handling below.
        return ApplyOutcome(ok=False, message=str(exc))
    desktop_assignment = {
        resolved[pattern]: names for pattern, names in profile.desktop_assignment.items()
    }
    try:
        reconcile.reconcile(active_monitors=order, desktop_assignment=desktop_assignment, order=order)
    except reconcile.ReconciliationError as exc:
        return ApplyOutcome(ok=False, message=str(exc))
    hooks.run_hooks(profile.hooks)
    return ApplyOutcome(ok=True, message="")


def replay_profile(profile: Profile) -> ApplyOutcome:
    state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
    resolved = resolve_targets(profile, state)
    order = [resolved[spec.edid_or_pattern] for spec in profile.outputs]
    overflow_target = next(
        resolved[spec.edid_or_pattern] for spec in profile.outputs if spec.primary
    )
    outputs = _outputs_for_apply(profile, resolved)
    outcome = apply_geometry(outputs, overflow_target=overflow_target, survivors=order)
    if not outcome.ok:
        return outcome
    return finish_reconciliation(profile, resolved, order)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/backend/test_apply.py -v`
Expected: 12 passed

- [ ] **Step 5: Run the full backend test suite**

Run: `.venv/bin/pytest tests/backend -v`
Expected: all tests from Tasks 2-11 pass (around 80 tests — the exact
count isn't load-bearing, just confirm zero failures).

- [ ] **Step 6: Commit**

```bash
git add src/bspwm_display_manager/backend/apply.py tests/backend/test_apply.py
git commit -m "$(cat <<'EOF'
Add apply orchestration (resolve targets, geometry, reconciliation)

Splits into apply_geometry (pre-confirm: retire + xrandr) and
finish_reconciliation (post-confirm: scale env + desktop reconciliation
+ hooks) so the GUI's confirm/revert safety net can gate the second half
without needing to gate the first. replay_profile chains both for the
CLI/daemon path, which skips the gate entirely.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 12: CLI `apply` command

**Files:**
- Create: `src/bspwm_display_manager/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `profile_store.load` (Task 7), `apply.replay_profile` (Task 11).
- Produces: `main(argv: list[str] | None = None) -> int` (registered as
  the `bspwm-display-manager` console script). Subcommand `apply <name>`
  is implemented now; subcommand `gui` is added in Task 18 once the UI
  exists.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

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

    return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: 4 passed

- [ ] **Step 5: Verify the console script resolves**

Run: `.venv/bin/pip install -e . && .venv/bin/bspwm-display-manager apply nonexistent`
Expected: prints a "no profile named" error to stderr, exits nonzero
(confirms the `pyproject.toml` `[project.scripts]` entry point works
end-to-end, not just `python -m`).

- [ ] **Step 6: Commit**

```bash
git add src/bspwm_display_manager/cli.py tests/test_cli.py
git commit -m "$(cat <<'EOF'
Add CLI apply command for sxhkd keybindings

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 13: Qt test scaffolding + pure snap geometry

**Files:**
- Create: `tests/conftest.py`
- Create: `src/bspwm_display_manager/ui/snap.py`
- Test: `tests/ui/test_snap.py`

**Interfaces:**
- Produces:
  - `qapp` pytest fixture (session-scoped `QApplication` under the
    `offscreen` Qt platform plugin, so every later widget test can
    instantiate widgets with no real X display)
  - `Rect(x: int, y: int, w: int, h: int)`
  - `compute_snap(dragged: Rect, others: list[Rect], threshold: int) -> tuple[int, int]`
    (pure geometry, no Qt — `canvas.py` in Task 14 converts to/from
    `QRectF`)

- [ ] **Step 1: Write `tests/conftest.py`**

```python
# tests/conftest.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: Write the failing snap tests**

```python
# tests/ui/test_snap.py
from bspwm_display_manager.ui.snap import Rect, compute_snap


def test_snaps_left_edge_to_others_right_edge_within_threshold():
    dragged = Rect(x=105, y=0, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (100, 0)


def test_no_snap_when_outside_threshold():
    dragged = Rect(x=150, y=0, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (150, 0)


def test_snaps_top_edge_to_others_bottom_edge():
    dragged = Rect(x=0, y=105, w=100, h=100)
    other = Rect(x=0, y=0, w=100, h=100)
    assert compute_snap(dragged, [other], threshold=10) == (0, 100)


def test_x_and_y_snap_independently():
    dragged = Rect(x=103, y=203, w=50, h=50)
    other = Rect(x=0, y=0, w=100, h=100)
    x, y = compute_snap(dragged, [other], threshold=10)
    assert x == 100
    assert y == 203


def test_picks_nearest_candidate_among_multiple_others():
    dragged = Rect(x=52, y=0, w=50, h=50)
    near = Rect(x=0, y=0, w=50, h=50)
    far = Rect(x=200, y=0, w=50, h=50)
    x, _ = compute_snap(dragged, [near, far], threshold=10)
    assert x == 50
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_snap.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Write the implementation**

```python
# src/bspwm_display_manager/ui/snap.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int


def compute_snap(dragged: Rect, others: list[Rect], threshold: int) -> tuple[int, int]:
    best_dx: int | None = None
    best_dy: int | None = None
    for other in others:
        for candidate_x in (other.x, other.x + other.w, other.x - dragged.w, other.x + other.w - dragged.w):
            dx = candidate_x - dragged.x
            if abs(dx) <= threshold and (best_dx is None or abs(dx) < abs(best_dx)):
                best_dx = dx
        for candidate_y in (other.y, other.y + other.h, other.y - dragged.h, other.y + other.h - dragged.h):
            dy = candidate_y - dragged.y
            if abs(dy) <= threshold and (best_dy is None or abs(dy) < abs(best_dy)):
                best_dy = dy
    new_x = dragged.x + best_dx if best_dx is not None else dragged.x
    new_y = dragged.y + best_dy if best_dy is not None else dragged.y
    return new_x, new_y
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_snap.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add tests/conftest.py src/bspwm_display_manager/ui/snap.py tests/ui/test_snap.py
git commit -m "$(cat <<'EOF'
Add offscreen Qt test fixture and pure canvas snap geometry

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 14: Layout canvas (drag-arrange)

**Files:**
- Create: `src/bspwm_display_manager/ui/canvas.py`
- Test: `tests/ui/test_canvas.py`

**Interfaces:**
- Consumes: `Rect`, `compute_snap` (Task 13); `Output` (Task 2).
- Produces:
  - `MonitorItem(QGraphicsRectItem)` — one per connected output, draggable,
    stores `output_name`, emits snapping via `compute_snap` on move.
  - `DisplayCanvas(QGraphicsView)`
    - `set_outputs(outputs: list[Output]) -> None` — rebuilds the scene
      from scratch, one `MonitorItem` per output, scaled down to fit the
      view (real pixel positions divided by a fixed `SCALE_DOWN` factor).
    - `positions() -> dict[str, tuple[int, int]]` — reads back each
      item's current scene position, scaled back up to real pixels.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_canvas.py
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.canvas import DisplayCanvas


def _output(name, w, h, x, y):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=x, y=y, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_set_outputs_creates_one_item_per_output(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([
        _output("DP-1", 2560, 1440, 0, 0),
        _output("eDP-1", 1920, 1200, 2560, 0),
    ])
    assert len(canvas.scene().items()) == 2


def test_positions_round_trips_through_the_scale_factor(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 100, 200)])
    assert canvas.positions() == {"DP-1": (100, 200)}


def test_positions_round_trips_a_position_not_divisible_by_scale_down(qapp):
    """SCALE_DOWN is 10 -- a position like x=105 isn't a clean multiple
    of it. Regression test for a version that used integer floor
    division on the way in (out.x // SCALE_DOWN, discarding the
    remainder) and couldn't recover it on the way out; 105 silently
    became 100. Real monitor positions are not guaranteed to land on
    multiples of 10."""
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 105, 207)])
    assert canvas.positions() == {"DP-1": (105, 207)}


def test_set_outputs_clears_previous_items(qapp):
    canvas = DisplayCanvas()
    canvas.set_outputs([_output("DP-1", 2560, 1440, 0, 0)])
    canvas.set_outputs([_output("eDP-1", 1920, 1200, 0, 0)])
    assert len(canvas.scene().items()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_canvas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/ui/canvas.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView,
)

from bspwm_display_manager.backend.models import Output
from bspwm_display_manager.ui.snap import Rect, compute_snap

SCALE_DOWN = 10  # 1 scene unit == 10 real pixels, keeps a 4K desktop on-screen
SNAP_THRESHOLD = 15  # scene units


class MonitorItem(QGraphicsRectItem):
    def __init__(self, output_name: str, w: float, h: float):
        super().__init__(0, 0, w, h)
        self.output_name = output_name
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene() is not None:
            # Rounded to int here for the snap-candidate arithmetic only
            # (snapping is threshold-based, not exact); real-pixel
            # positions stay float scene coordinates everywhere else so
            # positions() can round-trip a value that isn't a multiple
            # of SCALE_DOWN.
            others = [
                Rect(round(item.x()), round(item.y()), round(item.rect().width()), round(item.rect().height()))
                for item in self.scene().items()
                if isinstance(item, MonitorItem) and item is not self
            ]
            dragged = Rect(round(value.x()), round(value.y()),
                            round(self.rect().width()), round(self.rect().height()))
            snapped_x, snapped_y = compute_snap(dragged, others, SNAP_THRESHOLD)
            value.setX(snapped_x)
            value.setY(snapped_y)
        return super().itemChange(change, value)


class DisplayCanvas(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

    def set_outputs(self, outputs: list[Output]) -> None:
        self._scene.clear()
        for out in outputs:
            mode = out.current_mode() or out.preferred_mode()
            if mode is None:
                continue
            # True (float) division, not floor division: a position or
            # size that isn't a multiple of SCALE_DOWN must still
            # round-trip exactly through positions() below. Floor
            # division would discard the remainder permanently.
            item = MonitorItem(out.name, mode.width / SCALE_DOWN, mode.height / SCALE_DOWN)
            item.setPos(out.x / SCALE_DOWN, out.y / SCALE_DOWN)
            self._scene.addItem(item)

    def positions(self) -> dict[str, tuple[int, int]]:
        result = {}
        for item in self._scene.items():
            if isinstance(item, MonitorItem):
                # round(), not int(): item.x()/y() are floats and binary
                # floating point can't represent every decimal exactly
                # (e.g. 10.7), but the error is many orders of magnitude
                # smaller than 0.5, so round() always recovers the exact
                # original integer pixel value.
                result[item.output_name] = (round(item.x() * SCALE_DOWN), round(item.y() * SCALE_DOWN))
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_canvas.py -v`
Expected: 4 passed

- [ ] **Step 5: Manual verification**

Run: `.venv/bin/python -c "
from PySide6.QtWidgets import QApplication
from bspwm_display_manager.ui.canvas import DisplayCanvas
from bspwm_display_manager.backend.models import Mode, Output
app = QApplication([])
c = DisplayCanvas()
c.set_outputs([Output(name='eDP-1', connected=True, primary=True, edid='e', x=0, y=0,
                       rotation='normal', scale_x=1.0, scale_y=1.0,
                       modes=[Mode(1920,1200,60.03,'0x1',True,True)])])
c.show()
app.exec()
"`
Expected: a window opens showing one rectangle representing the laptop
panel; dragging it moves it; it snaps when dropped near where a second
rectangle would be (retest with two outputs once a second monitor is
available, e.g. at the office).

- [ ] **Step 6: Commit**

```bash
git add src/bspwm_display_manager/ui/canvas.py tests/ui/test_canvas.py
git commit -m "$(cat <<'EOF'
Add drag-arrange display canvas with edge snapping

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 15: Output config panel + session scale control

**Files:**
- Create: `src/bspwm_display_manager/ui/output_panel.py`
- Create: `src/bspwm_display_manager/ui/scale_control.py`
- Test: `tests/ui/test_output_panel.py`
- Test: `tests/ui/test_scale_control.py`

**Interfaces:**
- Consumes: `Output`, `Mode` (Task 2); `suggest_global_scale` (Task 6).
- Produces:
  - `OutputPanel(QWidget)` — `set_output(output: Output) -> None`;
    mode/rate combo boxes populated from `output.modes`; a `primary`
    checkbox; a `blurry_scale_enabled` checkbox that reveals a per-output
    scale spin box (secondary/fallback mechanism from the spec).
    `current_selection() -> dict` returns the edited values.
  - `SessionScaleControl(QWidget)` — `set_outputs(outputs: list[Output]) -> None`
    computes and displays the suggested percent via
    `suggest_global_scale`; `value() -> int` returns the user's chosen
    percent (defaults to the suggestion until changed).

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/test_output_panel.py
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.output_panel import OutputPanel


def _output():
    modes = [
        Mode(width=2560, height=1440, rate=59.95, id="0x1", current=True, preferred=True),
        Mode(width=1920, height=1080, rate=60.0, id="0x2", current=False, preferred=False),
    ]
    return Output(name="DP-1", connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=modes)


def test_set_output_populates_mode_choices(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    assert panel.mode_combo.count() == 2


def test_current_selection_defaults_to_the_outputs_current_mode(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    sel = panel.current_selection()
    assert sel["mode"] == (2560, 1440)
    assert sel["rate"] == 59.95
    assert sel["primary"] is False


def test_blurry_scale_hidden_until_opted_in(qapp):
    panel = OutputPanel()
    panel.set_output(_output())
    assert panel.scale_spin.isVisibleTo(panel) is False
    panel.blurry_scale_checkbox.setChecked(True)
    assert panel.scale_spin.isVisibleTo(panel) is True
```

```python
# tests/ui/test_scale_control.py
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.ui.scale_control import SessionScaleControl


def _output(name, w, h):
    mode = Mode(width=w, height=h, rate=60.0, id="0x1", current=True, preferred=True)
    return Output(name=name, connected=True, primary=False, edid="e",
                  x=0, y=0, rotation="normal", scale_x=1.0, scale_y=1.0, modes=[mode])


def test_defaults_to_the_suggested_percent(qapp):
    control = SessionScaleControl()
    control.set_outputs([_output("DP-1", 2560, 1440), _output("DP-2", 3840, 2160)])
    assert control.value() == 150


def test_user_choice_overrides_the_suggestion(qapp):
    control = SessionScaleControl()
    control.set_outputs([_output("DP-1", 2560, 1440), _output("DP-2", 3840, 2160)])
    control.combo.setCurrentText("100%")
    assert control.value() == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_output_panel.py tests/ui/test_scale_control.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/ui/output_panel.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QWidget,
)

from bspwm_display_manager.backend.models import Output


class OutputPanel(QWidget):
    def __init__(self):
        super().__init__()
        self.output: Output | None = None  # public: main_window reads this
        # to know which output the panel's current edits apply to.
        self.mode_combo = QComboBox()
        self.rate_combo = QComboBox()
        self.primary_checkbox = QCheckBox("Primary")
        self.blurry_scale_checkbox = QCheckBox("Enable per-output scale (blurry)")
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.5, 2.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setVisible(False)
        self.blurry_scale_checkbox.toggled.connect(self.scale_spin.setVisible)
        self.mode_combo.currentIndexChanged.connect(self._refresh_rate_choices)

        layout = QFormLayout(self)
        layout.addRow("Mode", self.mode_combo)
        layout.addRow("Refresh rate", self.rate_combo)
        layout.addRow(self.primary_checkbox)
        layout.addRow(self.blurry_scale_checkbox)
        layout.addRow("Per-output scale", self.scale_spin)

    def set_output(self, output: Output) -> None:
        self.output = output
        self.mode_combo.clear()
        seen_resolutions: list[tuple[int, int]] = []
        for mode in output.modes:
            res = (mode.width, mode.height)
            if res not in seen_resolutions:
                seen_resolutions.append(res)
                self.mode_combo.addItem(f"{mode.width}x{mode.height}", res)
        current = output.current_mode()
        if current is not None:
            idx = self.mode_combo.findData((current.width, current.height))
            if idx >= 0:
                self.mode_combo.setCurrentIndex(idx)
        self.primary_checkbox.setChecked(output.primary)
        self._refresh_rate_choices()

    def _refresh_rate_choices(self) -> None:
        if self.output is None:
            return
        res = self.mode_combo.currentData()
        self.rate_combo.clear()
        if res is None:
            return
        for mode in self.output.modes:
            if (mode.width, mode.height) == res:
                self.rate_combo.addItem(f"{mode.rate:g}Hz", mode.rate)
        current = self.output.current_mode()
        if current is not None and (current.width, current.height) == res:
            idx = self.rate_combo.findData(current.rate)
            if idx >= 0:
                self.rate_combo.setCurrentIndex(idx)

    def current_selection(self) -> dict:
        return {
            "mode": self.mode_combo.currentData(),
            "rate": self.rate_combo.currentData(),
            "primary": self.primary_checkbox.isChecked(),
            "scale": self.scale_spin.value() if self.blurry_scale_checkbox.isChecked() else 1.0,
        }
```

```python
# src/bspwm_display_manager/ui/scale_control.py
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget

from bspwm_display_manager.backend.models import Output
from bspwm_display_manager.backend.scale import suggest_global_scale

_CHOICES = [100, 125, 150, 175, 200]


class SessionScaleControl(QWidget):
    def __init__(self):
        super().__init__()
        self.combo = QComboBox()
        for pct in _CHOICES:
            self.combo.addItem(f"{pct}%", pct)
        layout = QFormLayout(self)
        layout.addRow("Session scale", self.combo)

    def set_outputs(self, outputs: list[Output]) -> None:
        suggested = suggest_global_scale(outputs)
        idx = self.combo.findData(suggested)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def value(self) -> int:
        return self.combo.currentData()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_output_panel.py tests/ui/test_scale_control.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/ui/output_panel.py src/bspwm_display_manager/ui/scale_control.py tests/ui/test_output_panel.py tests/ui/test_scale_control.py
git commit -m "$(cat <<'EOF'
Add per-output config panel and session scale control

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 16: Desktop assignment panel

This is the UI for the literal feature the user asked for — which
desktops go on which display, per profile. Order in the list matters: it
sets each desktop's positional index, which `sxhkdrc`'s `super+{1-3}` →
`bspc desktop -f '^{1-3}'` binding relies on.

**Files:**
- Create: `src/bspwm_display_manager/ui/desktop_panel.py`
- Test: `tests/ui/test_desktop_panel.py`

**Interfaces:**
- Produces: `DesktopAssignmentPanel(QWidget)`
  - `set_monitors(names: list[str]) -> None`
  - `load_assignment(assignment: dict[str, list[str]]) -> None`
  - `assignment() -> dict[str, list[str]]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/test_desktop_panel.py
from bspwm_display_manager.ui.desktop_panel import DesktopAssignmentPanel


def test_load_assignment_populates_list_for_selected_monitor(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1", "DP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat", "media"], "DP-1": ["pm"]})
    panel.monitor_combo.setCurrentText("eDP-1")
    names = [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]
    assert names == ["term", "chat", "media"]


def test_add_desktop_appends_to_current_monitor(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term"]})
    panel.name_input.setText("chat")
    panel._add_desktop()
    assert panel.assignment()["eDP-1"] == ["term", "chat"]


def test_remove_selected_deletes_the_current_row(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat"]})
    panel.list_widget.setCurrentRow(0)
    panel._remove_selected()
    assert panel.assignment()["eDP-1"] == ["chat"]


def test_move_selected_swaps_order_and_keeps_selection_on_the_moved_item(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat", "media"]})
    panel.list_widget.setCurrentRow(0)
    panel._move_selected(1)
    assert panel.assignment()["eDP-1"] == ["chat", "term", "media"]
    assert panel.list_widget.currentRow() == 1


def test_move_selected_at_the_boundary_is_a_no_op(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1"])
    panel.load_assignment({"eDP-1": ["term", "chat"]})
    panel.list_widget.setCurrentRow(0)
    panel._move_selected(-1)
    assert panel.assignment()["eDP-1"] == ["term", "chat"]


def test_switching_monitor_shows_that_monitors_own_list(qapp):
    panel = DesktopAssignmentPanel()
    panel.set_monitors(["eDP-1", "DP-1"])
    panel.load_assignment({"eDP-1": ["term"], "DP-1": ["pm", "office"]})
    panel.monitor_combo.setCurrentText("DP-1")
    names = [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]
    assert names == ["pm", "office"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_desktop_panel.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/ui/desktop_panel.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLineEdit, QListWidget, QPushButton, QVBoxLayout, QWidget,
)


class DesktopAssignmentPanel(QWidget):
    def __init__(self):
        super().__init__()
        self._assignment: dict[str, list[str]] = {}

        self.monitor_combo = QComboBox()
        self.list_widget = QListWidget()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("desktop name")
        self.add_button = QPushButton("Add")
        self.remove_button = QPushButton("Remove")
        self.up_button = QPushButton("Move Up")
        self.down_button = QPushButton("Move Down")

        self.monitor_combo.currentTextChanged.connect(lambda _: self._refresh_list())
        self.add_button.clicked.connect(self._add_desktop)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(lambda: self._move_selected(-1))
        self.down_button.clicked.connect(lambda: self._move_selected(1))

        add_row = QHBoxLayout()
        add_row.addWidget(self.name_input)
        add_row.addWidget(self.add_button)
        button_row = QHBoxLayout()
        button_row.addWidget(self.remove_button)
        button_row.addWidget(self.up_button)
        button_row.addWidget(self.down_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.monitor_combo)
        layout.addWidget(self.list_widget)
        layout.addLayout(add_row)
        layout.addLayout(button_row)

    def set_monitors(self, names: list[str]) -> None:
        self.monitor_combo.clear()
        self.monitor_combo.addItems(names)

    def load_assignment(self, assignment: dict[str, list[str]]) -> None:
        self._assignment = {mon: list(names) for mon, names in assignment.items()}
        self._refresh_list()

    def assignment(self) -> dict[str, list[str]]:
        return {mon: list(names) for mon, names in self._assignment.items()}

    def _current_monitor(self) -> str | None:
        return self.monitor_combo.currentText() or None

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        mon = self._current_monitor()
        if mon is None:
            return
        for name in self._assignment.get(mon, []):
            self.list_widget.addItem(name)

    def _add_desktop(self) -> None:
        name = self.name_input.text().strip()
        mon = self._current_monitor()
        if not name or mon is None:
            return
        self._assignment.setdefault(mon, []).append(name)
        self.name_input.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        mon = self._current_monitor()
        row = self.list_widget.currentRow()
        if mon is None or row < 0:
            return
        del self._assignment[mon][row]
        self._refresh_list()

    def _move_selected(self, delta: int) -> None:
        mon = self._current_monitor()
        row = self.list_widget.currentRow()
        if mon is None or row < 0:
            return
        names = self._assignment[mon]
        new_row = row + delta
        if 0 <= new_row < len(names):
            names[row], names[new_row] = names[new_row], names[row]
            self._refresh_list()
            self.list_widget.setCurrentRow(new_row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_desktop_panel.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/ui/desktop_panel.py tests/ui/test_desktop_panel.py
git commit -m "$(cat <<'EOF'
Add desktop-to-monitor assignment panel

Per-monitor ordered desktop list editor; order is preserved since
sxhkdrc's super+{1-3} bindings target desktops by positional index.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 17: Apply confirm/revert dialog

**Files:**
- Create: `src/bspwm_display_manager/ui/apply_dialog.py`
- Test: `tests/ui/test_apply_dialog.py`

**Interfaces:**
- Produces:
  - `remaining_seconds(elapsed: int, timeout: int) -> int` (pure, tested
    with no Qt involvement)
  - `ApplyConfirmDialog(QDialog)`, constructed with `timeout_seconds: int = 15, parent=None` (the `parent` kwarg is required so Task 18's `MainWindow` can pass `parent=self`)
    - `start() -> None` — begins the countdown
    - `was_confirmed() -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# tests/ui/test_apply_dialog.py
from bspwm_display_manager.ui.apply_dialog import ApplyConfirmDialog, remaining_seconds


def test_remaining_seconds_counts_down_to_zero():
    assert remaining_seconds(0, 15) == 15
    assert remaining_seconds(5, 15) == 10
    assert remaining_seconds(20, 15) == 0


def test_label_reflects_elapsed_time(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=15)
    dialog._elapsed = 5
    dialog._update_label()
    assert "10s" in dialog.label.text()


def test_confirm_marks_confirmed_and_accepts(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=15)
    dialog._confirm()
    assert dialog.was_confirmed() is True
    assert dialog.result() == dialog.DialogCode.Accepted


def test_ticking_past_the_timeout_rejects_without_confirming(qapp):
    dialog = ApplyConfirmDialog(timeout_seconds=2)
    dialog._tick()
    dialog._tick()
    assert dialog.was_confirmed() is False
    assert dialog.result() == dialog.DialogCode.Rejected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/ui/test_apply_dialog.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
# src/bspwm_display_manager/ui/apply_dialog.py
from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout


def remaining_seconds(elapsed: int, timeout: int) -> int:
    return max(0, timeout - elapsed)


class ApplyConfirmDialog(QDialog):
    def __init__(self, timeout_seconds: int = 15, parent=None):
        super().__init__(parent)
        self.timeout_seconds = timeout_seconds
        self._elapsed = 0
        self._confirmed = False

        self.label = QLabel()
        self.keep_button = QPushButton("Keep these settings")
        self.revert_button = QPushButton("Revert now")
        self.keep_button.clicked.connect(self._confirm)
        self.revert_button.clicked.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self.keep_button)
        buttons.addWidget(self.revert_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addLayout(buttons)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._update_label()

    def start(self) -> None:
        self._elapsed = 0
        self._timer.start()

    def _tick(self) -> None:
        self._elapsed += 1
        self._update_label()
        if remaining_seconds(self._elapsed, self.timeout_seconds) <= 0:
            self._timer.stop()
            self.reject()

    def _update_label(self) -> None:
        remaining = remaining_seconds(self._elapsed, self.timeout_seconds)
        self.label.setText(f"Keep these display settings? Reverting in {remaining}s.")

    def _confirm(self) -> None:
        self._confirmed = True
        self._timer.stop()
        self.accept()

    def was_confirmed(self) -> bool:
        return self._confirmed
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_apply_dialog.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/bspwm_display_manager/ui/apply_dialog.py tests/ui/test_apply_dialog.py
git commit -m "$(cat <<'EOF'
Add apply confirm/revert countdown dialog

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 18: Main window + GUI entry point

Wires every widget from Tasks 14-17 to the backend from Tasks 2-11.
Correctness here is primarily verified manually (per the spec's testing
section — this is real system integration, not unit-testable business
logic); the automated test only guards against import/wiring breakage.

**Files:**
- Create: `src/bspwm_display_manager/ui/main_window.py`
- Create: `src/bspwm_display_manager/ui/app.py`
- Modify: `src/bspwm_display_manager/cli.py` (add `gui` subcommand)
- Test: `tests/ui/test_main_window.py`

**Interfaces:**
- Consumes: everything from Tasks 2-11 and 14-17.
- Produces: `MainWindow(QMainWindow)`; `run() -> int` in `app.py`; `cli.py`
  gains a `gui` subcommand.

- [ ] **Step 1: Write the failing test**

```python
# tests/ui/test_main_window.py
from pathlib import Path
from unittest.mock import patch

FIXTURE = (Path(__file__).parent.parent / "fixtures" / "xrandr_verbose_single_laptop.txt").read_text()


def test_main_window_constructs_and_populates_from_system_state(qapp):
    from bspwm_display_manager.ui.main_window import MainWindow

    with patch("bspwm_display_manager.ui.main_window.xrandr_client.query_verbose", return_value=FIXTURE), \
         patch("bspwm_display_manager.ui.main_window.bspc_client.query_desktop_names", return_value=["term"]), \
         patch("bspwm_display_manager.ui.main_window.profile_store.list_profiles", return_value=["home"]):
        window = MainWindow()

    assert len(window.canvas.scene().items()) == 1
    assert window.load_combo.count() == 1
    assert window.desktop_panel.assignment() == {"eDP-1": ["term"]}


def test_collect_outputs_for_apply_forces_other_outputs_non_primary_when_selected_becomes_primary(qapp):
    """Regression test: xrandr rejects (or behaves ambiguously on) a
    command with more than one --primary flag. eDP-1 is primary in the
    dual_office fixture; selecting DP-1 in output_select_combo and
    checking its Primary box must clear eDP-1's primary flag in the
    outputs _collect_outputs_for_apply builds, not just add a second
    one."""
    from bspwm_display_manager.ui.main_window import MainWindow

    fixture = (Path(__file__).parent.parent / "fixtures" / "xrandr_verbose_dual_office.txt").read_text()
    with patch("bspwm_display_manager.ui.main_window.xrandr_client.query_verbose", return_value=fixture), \
         patch("bspwm_display_manager.ui.main_window.bspc_client.query_desktop_names", return_value=[]), \
         patch("bspwm_display_manager.ui.main_window.profile_store.list_profiles", return_value=[]):
        window = MainWindow()

    window.output_select_combo.setCurrentText("DP-1")
    assert window.output_panel.output.name == "DP-1"
    window.output_panel.primary_checkbox.setChecked(True)

    outputs = window._collect_outputs_for_apply()
    primaries = [o.name for o in outputs if o.primary]
    assert primaries == ["DP-1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/ui/test_main_window.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write `main_window.py`**

```python
# src/bspwm_display_manager/ui/main_window.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QInputDialog, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from bspwm_display_manager.backend import apply, bspc_client, edid, profile_store
from bspwm_display_manager.backend import xrandr_client, xrandr_parser
from bspwm_display_manager.backend.models import Mode, Output
from bspwm_display_manager.backend.profile import OutputSpec, Profile
from bspwm_display_manager.ui.apply_dialog import ApplyConfirmDialog
from bspwm_display_manager.ui.canvas import DisplayCanvas
from bspwm_display_manager.ui.desktop_panel import DesktopAssignmentPanel
from bspwm_display_manager.ui.output_panel import OutputPanel
from bspwm_display_manager.ui.scale_control import SessionScaleControl

PROFILES_DIR = Path.home() / ".config" / "bspwm-display-manager" / "profiles"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("bspwm Display Manager")

        self.canvas = DisplayCanvas()
        self.output_select_combo = QComboBox()
        self.output_panel = OutputPanel()
        self.scale_control = SessionScaleControl()
        self.desktop_panel = DesktopAssignmentPanel()
        self.apply_button = QPushButton("Apply")
        self.save_button = QPushButton("Save Profile")
        self.load_combo = QComboBox()
        self.load_button = QPushButton("Load")

        self.output_select_combo.currentTextChanged.connect(self._on_output_selected)
        self.apply_button.clicked.connect(self._on_apply)
        self.save_button.clicked.connect(self._on_save)
        self.load_button.clicked.connect(self._on_load)

        side = QVBoxLayout()
        side.addWidget(self.output_select_combo)
        side.addWidget(self.output_panel)
        side.addWidget(self.scale_control)
        side.addWidget(self.desktop_panel)
        side.addWidget(self.apply_button)
        side.addWidget(self.save_button)
        load_row = QHBoxLayout()
        load_row.addWidget(self.load_combo)
        load_row.addWidget(self.load_button)
        side.addLayout(load_row)

        root = QHBoxLayout()
        root.addWidget(self.canvas, stretch=2)
        side_widget = QWidget()
        side_widget.setLayout(side)
        root.addWidget(side_widget, stretch=1)

        central = QWidget()
        central.setLayout(root)
        self.setCentralWidget(central)

        self._last_good_outputs: list[Output] = []
        self._refresh_from_system()

    def _refresh_from_system(self) -> None:
        state = xrandr_parser.parse_verbose(xrandr_client.query_verbose())
        connected = state.connected()
        self._last_good_outputs = list(connected)

        self.canvas.set_outputs(connected)
        self.scale_control.set_outputs(connected)

        self.output_select_combo.blockSignals(True)
        self.output_select_combo.clear()
        self.output_select_combo.addItems([o.name for o in connected])
        self.output_select_combo.blockSignals(False)
        if connected:
            self.output_panel.set_output(connected[0])

        names = [o.name for o in connected]
        self.desktop_panel.set_monitors(names)
        self.desktop_panel.load_assignment(
            {name: bspc_client.query_desktop_names(monitor=name) for name in names}
        )

        self.load_combo.clear()
        self.load_combo.addItems(profile_store.list_profiles(PROFILES_DIR))

    def _on_output_selected(self, name: str) -> None:
        match = next((o for o in self._last_good_outputs if o.name == name), None)
        if match is not None:
            self.output_panel.set_output(match)

    def _collect_outputs_for_apply(self) -> list[Output]:
        """Builds the outputs to apply: each output's last-known geometry,
        with the canvas's dragged position and — for whichever output is
        currently loaded in output_panel — that panel's edited
        mode/rate/primary/scale merged in. output_panel edits only one
        output at a time; _on_output_selected keeps it in sync with
        output_select_combo.

        If the panel's edit makes the selected output primary, every
        OTHER output is forced non-primary here — xrandr rejects (or
        behaves ambiguously on) a command with more than one --primary
        flag, and _last_good_outputs may still have a stale primary on a
        different output from before this edit."""
        positions = self.canvas.positions()
        selected = self.output_panel.output
        selection = self.output_panel.current_selection() if selected is not None else None
        new_primary_forces_others_off = selection is not None and selection["primary"]

        outputs = []
        for out in self._last_good_outputs:
            x, y = positions.get(out.name, (out.x, out.y))
            if selected is not None and out.name == selected.name and selection["mode"] is not None:
                width, height = selection["mode"]
                mode = Mode(width=width, height=height, rate=selection["rate"],
                            id="", current=True, preferred=False)
                outputs.append(Output(
                    name=out.name, connected=True, primary=selection["primary"], edid=out.edid,
                    x=x, y=y, rotation=out.rotation,
                    scale_x=selection["scale"], scale_y=selection["scale"], modes=[mode],
                ))
            else:
                primary = False if new_primary_forces_others_off else out.primary
                outputs.append(Output(
                    name=out.name, connected=True, primary=primary, edid=out.edid,
                    x=x, y=y, rotation=out.rotation, scale_x=out.scale_x, scale_y=out.scale_y,
                    modes=out.modes,
                ))
        return outputs

    def _on_apply(self) -> None:
        outputs = self._collect_outputs_for_apply()
        order = [o.name for o in outputs]
        if not order:
            return
        primary = next((o.name for o in outputs if o.primary), order[0])

        outcome = apply.apply_geometry(outputs, overflow_target=primary, survivors=order)
        if not outcome.ok:
            QMessageBox.critical(self, "Apply failed", outcome.message)
            return

        dialog = ApplyConfirmDialog(parent=self)
        dialog.start()
        if dialog.exec() == dialog.DialogCode.Accepted:
            resolved = {o.name: o.name for o in outputs}
            profile = Profile(
                name="__pending__", fingerprint="", scale_percent=self.scale_control.value(),
                outputs=[], desktop_assignment=self.desktop_panel.assignment(), hooks=[],
            )
            reconcile_outcome = apply.finish_reconciliation(profile, resolved, order)
            if not reconcile_outcome.ok:
                QMessageBox.critical(self, "Apply failed", reconcile_outcome.message)
            self._last_good_outputs = outputs
        else:
            prev = self._last_good_outputs
            prev_order = [o.name for o in prev]
            prev_primary = next((o.name for o in prev if o.primary), prev_order[0])
            revert_outcome = apply.apply_geometry(prev, overflow_target=prev_primary, survivors=prev_order)
            if not revert_outcome.ok:
                # The single worst state this dialog exists to prevent:
                # a failed revert with no explanation. Always tell the
                # user, since there's no further fallback to try.
                QMessageBox.critical(self, "Revert failed", revert_outcome.message)
        self._refresh_from_system()

    def _on_save(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Profile", "Profile name:")
        if not ok or not name:
            return
        outputs = self._collect_outputs_for_apply()
        specs = []
        for out in outputs:
            mode = out.current_mode()
            if mode is None:
                continue
            specs.append(OutputSpec(
                edid_or_pattern=out.edid or out.name, mode=(mode.width, mode.height),
                rate=mode.rate, x=out.x, y=out.y, rotation=out.rotation,
                scale_x=out.scale_x, scale_y=out.scale_y, primary=out.primary,
            ))
        profile = Profile(
            name=name, fingerprint=edid.fingerprint(outputs),
            scale_percent=self.scale_control.value(), outputs=specs,
            desktop_assignment=self.desktop_panel.assignment(), hooks=[],
        )
        try:
            profile_store.save(profile, PROFILES_DIR)
        except OSError as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            return
        # Deliberately NOT a full _refresh_from_system(): that would
        # re-query live xrandr/bspc state and snap the canvas back to
        # the current on-screen layout, discarding the arrangement the
        # user just saved (and about to Apply). Only the profile list
        # needs to reflect the new save.
        self.load_combo.clear()
        self.load_combo.addItems(profile_store.list_profiles(PROFILES_DIR))

    def _on_load(self) -> None:
        name = self.load_combo.currentText()
        if not name:
            return
        try:
            profile = profile_store.load(name, PROFILES_DIR)
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        try:
            outcome = apply.replay_profile(profile)
        except ValueError as exc:
            QMessageBox.critical(self, "Apply failed", str(exc))
            return
        if not outcome.ok:
            QMessageBox.critical(self, "Apply failed", outcome.message)
        self._refresh_from_system()
```

- [ ] **Step 4: Write `app.py`**

```python
# src/bspwm_display_manager/ui/app.py
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from bspwm_display_manager.ui.main_window import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
```

- [ ] **Step 5: Add the `gui` subcommand to `cli.py`**

```python
# in src/bspwm_display_manager/cli.py, inside main(), after the "apply" subparser is added:
    sub.add_parser("gui", help="launch the GUI")
```

```python
# and inside main(), replace the trailing `return 1` with:
    if args.command == "gui":
        from bspwm_display_manager.ui.app import run
        return run()

    return 1
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/ui/test_main_window.py -v`
Expected: 2 passed

Run: `.venv/bin/pytest tests/test_cli.py -v`
Expected: still 4 passed (the `gui` subcommand has no automated test —
it launches a real Qt event loop, verified manually in Step 7)

- [ ] **Step 7: Manual verification**

Run: `.venv/bin/bspwm-display-manager gui`
Expected: the window opens showing the laptop panel as one rectangle in
the canvas, mode/rate dropdowns populated, a "term" (or whatever's
currently assigned) desktop list, and a working Apply button that
re-applies the current layout with the 15-second confirm/revert dialog
appearing afterward. Re-verify the full flow (drag-arrange, Save
Profile, Load Profile, multi-monitor desktop assignment) once a second
monitor is available — this laptop alone can't exercise the
multi-output paths.

- [ ] **Step 8: Commit**

```bash
git add src/bspwm_display_manager/ui/main_window.py src/bspwm_display_manager/ui/app.py src/bspwm_display_manager/cli.py tests/ui/test_main_window.py
git commit -m "$(cat <<'EOF'
Wire main window and add gui CLI subcommand

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Task 19: README and sxhkd migration instructions

**Files:**
- Create: `README.md`

**Interfaces:**
- Produces: no code; this is the user-facing install/usage/migration doc.

- [ ] **Step 1: Write `README.md`**

```markdown
# bspwm-display-manager

A GUI (and CLI) for arranging bspwm's connected displays: drag to
position monitors, pick resolution/refresh rate, set a session-wide
scale factor (with a per-output blurry fallback for mismatched panel
ratios), assign bspwm desktops to specific monitors, and save/replay the
whole thing as a named profile.

Built for X11/bspwm, which has no per-monitor fractional scaling (see
`docs/superpowers/specs/2026-09-05-bspwm-display-manager-design.md` for
why, and what this tool does about it instead).

## Install

    python -m venv .venv
    .venv/bin/pip install -e .

## Usage

    bspwm-display-manager gui              # arrange displays, assign desktops, save profiles
    bspwm-display-manager apply <name>     # instantly replay a saved profile (for keybindings)

Profiles live in `~/.config/bspwm-display-manager/profiles/*.json`.

## Migrating from hand-written screenlayout scripts

If you have existing `~/.screenlayout/*.sh` + `bsp-assign-desktops` /
`bsp-retire-monitors` scripts (this project started as a generalization
of exactly that setup):

1. Launch `bspwm-display-manager gui`, arrange each layout the way the
   corresponding script did, and **Save Profile** under the same name
   (e.g. `work`, `home`).
2. Verify `bspwm-display-manager apply work` (and `home`) behave the way
   the old script did — check window placement across a few real
   monitor swaps before trusting it as a daily driver.
3. In `~/.config/bspwm/sxhkdrc`, change:

       super + ctrl + w
           bash ~/.screenlayout/work-layout.sh

       super + ctrl + h
           bash ~/.screenlayout/home-layout.sh

   to:

       super + ctrl + w
           bspwm-display-manager apply work

       super + ctrl + h
           bspwm-display-manager apply home

4. Reload sxhkd (`pkill -USR1 -x sxhkd`, or however your config reloads it).

The original scripts are left untouched on disk as a fallback — nothing
in this project deletes or modifies them.

## Development

    .venv/bin/pip install -e ".[dev]"
    .venv/bin/pytest
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "$(cat <<'EOF'
Add README with install, usage, and migration instructions

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01GeNU1czSEoSe9ivX3Zow2w
EOF
)"
```

---

## Self-Review Notes

**Spec coverage:** Canvas arrangement (Task 14), mode/refresh selection
(Task 15), global-scale + per-output blurry fallback (Tasks 5, 15), EDID
fingerprinting (Task 6), profile store (Task 7), Desktop Reconciliation
with every prior-art edge case (Task 9), post-apply hooks (Task 10),
apply orchestration + confirm/revert safety net (Tasks 11, 17), CLI for
keybindings (Task 12), desktop-to-monitor assignment UI (Task 16), full
GUI wiring (Task 18), migration instructions (Task 19). The Hotplug
Daemon component from the spec is deliberately excluded — it's the
separate follow-up plan noted in this plan's Architecture section.

**Type consistency check:** `Output`/`Mode`/`LayoutState` (Task 2) are
used with the same field names through every later task (`apply.py`,
`canvas.py`, `output_panel.py`, `main_window.py`) — verified by re-reading
each task's dataclass field usage against Task 2's definition.
`resolve_targets` returns `dict[str, str]` (pattern → real name)
consistently in Task 11's implementation and Task 18's `_on_apply`/`_on_save`
(which build the trivial identity mapping `{name: name}` since by that
point the outputs are already resolved). `Profile.desktop_assignment` keys
are `edid_or_pattern` strings in the stored JSON (Task 7) but real monitor
names once resolved for `reconcile.reconcile` (Task 9/11) — `apply.py`'s
`finish_reconciliation` is the one place that translates between the two,
consistently.

**Placeholder scan:** no TODO/TBD; every step has runnable code.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-05-bspwm-display-manager-core.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per
task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using
executing-plans, batch execution with checkpoints.

**Which approach?**
