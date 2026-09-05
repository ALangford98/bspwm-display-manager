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
