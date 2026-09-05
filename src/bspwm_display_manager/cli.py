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
