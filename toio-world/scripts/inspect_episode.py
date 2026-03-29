#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import inspect_episode


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a recorded toio episode.")
    parser.add_argument("episode_path")
    args = parser.parse_args()
    inspect_episode(path=Path(args.episode_path))


if __name__ == "__main__":
    main()
