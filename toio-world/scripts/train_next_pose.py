#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from toio_world.baseline import fit_mean_delta_model, save_mean_delta_model
from toio_world.logger import load_episode


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit a tiny next-pose baseline.")
    parser.add_argument("episode_path")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    bundle = load_episode(Path(args.episode_path))
    if not bundle.steps:
        raise SystemExit("No usable examples in episode.")

    model = fit_mean_delta_model([bundle])

    output_path = (
        Path(args.output)
        if args.output
        else Path(args.episode_path) / "baseline-next-pose.json"
    )
    save_mean_delta_model(model, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
