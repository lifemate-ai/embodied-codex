from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from .dataset import NextPoseExample, to_next_pose_examples
from .schema import EpisodeBundle


class ActionMeanDelta(BaseModel):
    count: int
    mean_dx: float
    mean_dy: float
    mean_dtheta_deg: float


class MeanDeltaModel(BaseModel):
    action_means: dict[str, ActionMeanDelta] = Field(default_factory=dict)
    episode_ids: list[str] = Field(default_factory=list)


class BaselineMetrics(BaseModel):
    examples: int
    mae_dx: float
    mae_dy: float
    mae_dtheta_deg: float


def fit_mean_delta_model(bundles: list[EpisodeBundle]) -> MeanDeltaModel:
    buckets: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for bundle in bundles:
        for example in to_next_pose_examples(bundle.steps):
            buckets[example.action_type].append(
                (example.target_dx, example.target_dy, example.target_dtheta_deg)
            )

    action_means: dict[str, ActionMeanDelta] = {}
    for action_type, values in buckets.items():
        count = len(values)
        action_means[action_type] = ActionMeanDelta(
            count=count,
            mean_dx=round(sum(value[0] for value in values) / count, 3),
            mean_dy=round(sum(value[1] for value in values) / count, 3),
            mean_dtheta_deg=round(sum(value[2] for value in values) / count, 3),
        )

    return MeanDeltaModel(
        action_means=action_means,
        episode_ids=[bundle.meta.episode_id for bundle in bundles],
    )


def evaluate_mean_delta_model(
    model: MeanDeltaModel,
    examples: list[NextPoseExample],
) -> BaselineMetrics:
    if not examples:
        return BaselineMetrics(examples=0, mae_dx=0.0, mae_dy=0.0, mae_dtheta_deg=0.0)

    total_abs_dx = 0.0
    total_abs_dy = 0.0
    total_abs_dtheta = 0.0
    count = 0

    for example in examples:
        stats = model.action_means.get(example.action_type)
        if stats is None:
            continue
        total_abs_dx += abs(example.target_dx - stats.mean_dx)
        total_abs_dy += abs(example.target_dy - stats.mean_dy)
        total_abs_dtheta += abs(example.target_dtheta_deg - stats.mean_dtheta_deg)
        count += 1

    if count == 0:
        return BaselineMetrics(examples=0, mae_dx=0.0, mae_dy=0.0, mae_dtheta_deg=0.0)

    return BaselineMetrics(
        examples=count,
        mae_dx=round(total_abs_dx / count, 3),
        mae_dy=round(total_abs_dy / count, 3),
        mae_dtheta_deg=round(total_abs_dtheta / count, 3),
    )


def save_mean_delta_model(model: MeanDeltaModel, path: str | Path) -> None:
    Path(path).write_text(json.dumps(model.model_dump(mode="json"), indent=2), encoding="utf-8")


def load_mean_delta_model(path: str | Path) -> MeanDeltaModel:
    return MeanDeltaModel.model_validate_json(Path(path).read_text(encoding="utf-8"))
