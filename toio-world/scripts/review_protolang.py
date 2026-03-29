#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import review_proto_language


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review top proto-language candidates for an episode."
    )
    parser.add_argument("episode_path")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-state-arity", type=int, default=2)
    args = parser.parse_args()
    review_proto_language(
        path=Path(args.episode_path),
        top_k=args.top_k,
        max_state_arity=args.max_state_arity,
    )


if __name__ == "__main__":
    main()
