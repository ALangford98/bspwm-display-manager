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
