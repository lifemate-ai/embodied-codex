#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import eval_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a next-pose baseline model.")
    parser.add_argument("model_path")
    parser.add_argument("episode_paths", nargs="+")
    args = parser.parse_args()
    eval_baseline(
        model_path=Path(args.model_path),
        paths=[Path(path) for path in args.episode_paths],
    )


if __name__ == "__main__":
    main()
