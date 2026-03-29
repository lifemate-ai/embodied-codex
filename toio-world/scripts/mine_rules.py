#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import mine_rules


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine simple transition rules from an episode.")
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--min-support", type=int, default=2)
    parser.add_argument("--min-confidence", type=float, default=0.8)
    parser.add_argument("--drop-low-value", action="store_true", default=True)
    parser.add_argument("--keep-low-value", action="store_false", dest="drop_low_value")
    parser.add_argument("--max-state-arity", type=int, default=2)
    args = parser.parse_args()
    mine_rules(
        path=Path(args.episode_path),
        output=Path(args.output) if args.output else None,
        min_support=args.min_support,
        min_confidence=args.min_confidence,
        drop_low_value=args.drop_low_value,
        max_state_arity=args.max_state_arity,
    )


if __name__ == "__main__":
    main()
