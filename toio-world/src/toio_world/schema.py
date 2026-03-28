from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "0.1.0"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Pose(BaseModel):
    x: float | None = None
    y: float | None = None
    theta_deg: float | None = None


class MarkerObservation(BaseModel):
    kind: str | None = None
    marker_id: str | None = None


class BatteryState(BaseModel):
    percent: int | None = None


class ExternalObservation(BaseModel):
    image_path: str | None = None
    topdown_image_path: str | None = None
    room: dict[str, Any] = Field(default_factory=dict)
    labels: list[str] = Field(default_factory=list)
    notes: dict[str, Any] = Field(default_factory=dict)


class CubeState(BaseModel):
    pose: Pose = Field(default_factory=Pose)
    marker: MarkerObservation = Field(default_factory=MarkerObservation)
    battery: BatteryState = Field(default_factory=BatteryState)


class ActionCommand(BaseModel):
    type: str
    left: int | None = None
    right: int | None = None
    duration_ms: int | None = None
    degrees: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DerivedTransition(BaseModel):
    dx: float | None = None
    dy: float | None = None
    dtheta_deg: float | None = None
    success: bool | None = None


class StepRecord(BaseModel):
    schema_version: str = SCHEMA_VERSION
    episode_id: str
    step: int
    ts: str
    pre: CubeState
    pre_observation: ExternalObservation = Field(default_factory=ExternalObservation)
    action: ActionCommand
    post: CubeState
    post_observation: ExternalObservation = Field(default_factory=ExternalObservation)
    derived: DerivedTransition


class EpisodeMeta(BaseModel):
    schema_version: str = SCHEMA_VERSION
    episode_id: str
    created_at: str
    backend: str
    policy_name: str
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    config_paths: dict[str, str] = Field(default_factory=dict)


class EpisodeBundle(BaseModel):
    meta: EpisodeMeta
    steps: list[StepRecord]
