#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import profile_actions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fit a calibration profile over one or more episodes."
    )
    parser.add_argument("episode_paths", nargs="+")
    parser.add_argument("--output", default="action-profile.json")
    args = parser.parse_args()
    profile_actions(
        paths=[Path(path) for path in args.episode_paths],
        output=Path(args.output),
    )


if __name__ == "__main__":
    main()
