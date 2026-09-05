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
