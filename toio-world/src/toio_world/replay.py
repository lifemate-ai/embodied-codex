from __future__ import annotations

from .controller import BaseController
from .schema import CubeState, StepRecord


def replay_steps(controller: BaseController, steps: list[StepRecord]) -> list[CubeState]:
    states: list[CubeState] = []
    controller.connect()
    try:
        for step in steps:
            states.append(controller.apply_action(step.action))
    finally:
        controller.disconnect()
    return states
