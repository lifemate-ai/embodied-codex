#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import collect_calibration


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect a repeated discrete-action calibration episode."
    )
    parser.add_argument("--episode-root", default="episodes")
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--world-config", default="configs/world.toml")
    args = parser.parse_args()
    collect_calibration(
        episode_root=Path(args.episode_root),
        backend=args.backend,
        repeats=args.repeats,
        world_config=Path(args.world_config),
    )


if __name__ == "__main__":
    main()
