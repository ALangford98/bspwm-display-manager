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
