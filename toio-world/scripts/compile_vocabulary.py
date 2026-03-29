#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import compile_vocabulary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compile symbols, concepts, macros, and rules into a working vocabulary."
    )
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--top-k-per-kind", type=int, default=10)
    parser.add_argument("--max-state-arity", type=int, default=2)
    args = parser.parse_args()
    compile_vocabulary(
        path=Path(args.episode_path),
        output=Path(args.output) if args.output else None,
        top_k_per_kind=args.top_k_per_kind,
        max_state_arity=args.max_state_arity,
    )


if __name__ == "__main__":
    main()
