from __future__ import annotations

import hashlib

from bspwm_display_manager.backend.models import Output


def fingerprint(outputs: list[Output]) -> str:
    edids = sorted(o.edid for o in outputs if o.edid)
    joined = "|".join(edids)
    return hashlib.sha256(joined.encode()).hexdigest()
