#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.cli import replay_episode


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a recorded toio episode.")
    parser.add_argument("episode_path")
    parser.add_argument("--backend", default="mock")
    args = parser.parse_args()
    replay_episode(path=Path(args.episode_path), backend=args.backend)


if __name__ == "__main__":
    main()
