#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import collect_pattern


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a named pattern episode.")
    parser.add_argument("policy_name", choices=["square", "spin", "random_walk"])
    parser.add_argument("--episode-root", default="episodes")
    parser.add_argument("--backend", default="mock")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--steps", type=int, default=32)
    args = parser.parse_args()
    collect_pattern(
        policy_name=args.policy_name,
        episode_root=Path(args.episode_root),
        backend=args.backend,
        repeats=args.repeats,
        steps=args.steps,
    )


if __name__ == "__main__":
    main()
