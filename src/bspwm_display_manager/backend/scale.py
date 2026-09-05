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
        if abs(ratio - clean_ratio) <= _TOLERANCE:
            return percent
    return 100
