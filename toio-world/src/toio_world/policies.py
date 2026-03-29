from __future__ import annotations

import random

from .calibration import build_calibration_sequence
from .schema import ActionCommand


def random_walk(*, steps: int, seed: int | None = None) -> list[ActionCommand]:
    rng = random.Random(seed)
    choices = [
        "forward_short",
        "forward_long",
        "backward_short",
        "turn_left_small",
        "turn_right_small",
        "turn_left_large",
        "turn_right_large",
        "stop",
    ]
    return [ActionCommand(type=rng.choice(choices)) for _ in range(steps)]


def square(*, repeats: int = 1) -> list[ActionCommand]:
    sequence: list[ActionCommand] = []
    for _ in range(repeats):
        for _ in range(4):
            sequence.append(ActionCommand(type="forward_long"))
            sequence.append(ActionCommand(type="turn_left_large"))
    return sequence


def spin(*, repeats: int = 8, direction: str = "left") -> list[ActionCommand]:
    action_type = "turn_left_small" if direction == "left" else "turn_right_small"
    return [ActionCommand(type=action_type) for _ in range(repeats)]


def calibration_sweep(*, repeats: int = 8) -> list[ActionCommand]:
    return [ActionCommand(type=action_type) for action_type in build_calibration_sequence(repeats)]


def build_policy(name: str, **kwargs: int) -> list[ActionCommand]:
    if name == "random_walk":
        return random_walk(steps=int(kwargs.get("steps", 32)), seed=kwargs.get("seed"))
    if name == "square":
        return square(repeats=int(kwargs.get("repeats", 1)))
    if name == "spin":
        return spin(
            repeats=int(kwargs.get("repeats", 8)),
            direction=str(kwargs.get("direction", "left")),
        )
    if name == "calibration_sweep":
        return calibration_sweep(repeats=int(kwargs.get("repeats", 8)))
    raise ValueError(f"Unknown policy: {name}")
