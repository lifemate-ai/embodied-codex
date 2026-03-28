#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import discover_macros


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover repeated action macros from an episode."
    )
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=2)
    parser.add_argument("--state-conditioned", action="store_true", default=True)
    parser.add_argument("--no-state-conditioned", action="store_false", dest="state_conditioned")
    args = parser.parse_args()
    discover_macros(
        path=Path(args.episode_path),
        output=Path(args.output) if args.output else None,
        min_support=args.min_support,
        max_length=args.max_length,
        state_conditioned=args.state_conditioned,
    )


if __name__ == "__main__":
    main()
