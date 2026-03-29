#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import derive_symbols


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Derive primitive proto-language symbols from an episode."
    )
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    parser.add_argument("--gloss-output", default=None)
    args = parser.parse_args()
    derive_symbols(
        path=Path(args.episode_path),
        output=Path(args.output) if args.output else None,
        gloss_output=Path(args.gloss_output) if args.gloss_output else None,
    )


if __name__ == "__main__":
    main()
