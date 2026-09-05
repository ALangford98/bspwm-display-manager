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
