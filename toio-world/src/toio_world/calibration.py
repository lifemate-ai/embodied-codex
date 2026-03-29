from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from .schema import EpisodeBundle, StepRecord

DISCRETE_ACTION_ORDER = [
    "forward_short",
    "forward_long",
    "backward_short",
    "turn_left_small",
    "turn_right_small",
    "turn_left_large",
    "turn_right_large",
]


class ActionCalibrationStats(BaseModel):
    action_type: str
    count: int
    success_rate: float
    mean_dx: float
    mean_dy: float
    mean_dtheta_deg: float
    std_dx: float
    std_dy: float
    std_dtheta_deg: float
    mean_distance: float
    std_distance: float
    suggested_scalar: float | None = None


class ActionCalibrationProfile(BaseModel):
    episode_ids: list[str] = Field(default_factory=list)
    actions: list[ActionCalibrationStats] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def build_calibration_sequence(repeats: int = 8) -> list[str]:
    sequence: list[str] = []
    for action_type in DISCRETE_ACTION_ORDER:
        sequence.extend([action_type] * repeats)
    return sequence


def fit_action_calibration_profile(bundles: list[EpisodeBundle]) -> ActionCalibrationProfile:
    by_action: dict[str, list[StepRecord]] = defaultdict(list)
    episode_ids: list[str] = []
    for bundle in bundles:
        episode_ids.append(bundle.meta.episode_id)
        for step in bundle.steps:
            by_action[step.action.type].append(step)

    actions: list[ActionCalibrationStats] = []
    for action_type in sorted(by_action):
        steps = by_action[action_type]
        dxs = [step.derived.dx or 0.0 for step in steps]
        dys = [step.derived.dy or 0.0 for step in steps]
        dthetas = [step.derived.dtheta_deg or 0.0 for step in steps]
        distances = [math.hypot(dx, dy) for dx, dy in zip(dxs, dys)]
        successes = [1.0 if step.derived.success else 0.0 for step in steps]
        actions.append(
            ActionCalibrationStats(
                action_type=action_type,
                count=len(steps),
                success_rate=round(_mean(successes), 3),
                mean_dx=round(_mean(dxs), 3),
                mean_dy=round(_mean(dys), 3),
                mean_dtheta_deg=round(_mean(dthetas), 3),
                std_dx=round(_std(dxs), 3),
                std_dy=round(_std(dys), 3),
                std_dtheta_deg=round(_std(dthetas), 3),
                mean_distance=round(_mean(distances), 3),
                std_distance=round(_std(distances), 3),
                suggested_scalar=_suggested_scalar(action_type, distances, dthetas),
            )
        )
    actions.sort(key=lambda item: item.action_type)
    return ActionCalibrationProfile(episode_ids=episode_ids, actions=actions)


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = _mean(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return math.sqrt(variance)


def _suggested_scalar(
    action_type: str,
    distances: list[float],
    dthetas: list[float],
) -> float | None:
    if action_type.startswith("turn_"):
        return round(_mean([abs(value) for value in dthetas]), 3)
    if "forward" in action_type or "backward" in action_type:
        return round(_mean(distances), 3)
    return None
