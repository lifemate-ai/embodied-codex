#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import discover_concepts


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover co-occurring state concepts.")
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument("--max-size", type=int, default=2)
    args = parser.parse_args()
    discover_concepts(
        path=Path(args.episode_path),
        output=Path(args.output) if args.output else None,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        max_size=args.max_size,
    )


if __name__ == "__main__":
    main()
