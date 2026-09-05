from __future__ import annotations

import re

from bspwm_display_manager.backend.models import LayoutState, Mode, Output

_OUTPUT_LINE = re.compile(
    r"^(?P<name>[A-Za-z0-9_-]+)\s+"
    r"(?P<status>connected|disconnected)\s*"
    r"(?P<primary>primary\s+)?"
    r"(?:(?P<w>\d+)x(?P<h>\d+)\+(?P<x>\d+)\+(?P<y>\d+)\s+)?"
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
            connected = m.group("status") == "connected"
            x = int(m.group("x")) if m.group("x") else 0
            y = int(m.group("y")) if m.group("y") else 0
            current = Output(
                name=m.group("name"),
                connected=connected,
                primary=bool(m.group("primary")),
                edid=None,
                x=x,
                y=y,
                rotation="normal",
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
            if is_current:
                current.x = current.x or current.x  # position already parsed from header
            pending_mode_header = None

    flush_edid()
    return LayoutState(outputs=outputs)
