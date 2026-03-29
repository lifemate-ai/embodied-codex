from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from pydantic import BaseModel, Field


class MotionConfig(BaseModel):
    forward_short_ms: int = 250
    forward_long_ms: int = 500
    backward_short_ms: int = 250
    turn_small_deg: int = 30
    turn_large_deg: int = 90
    move_speed: int = 30


class WorldConfig(BaseModel):
    schema_version: str = "0.1.0"
    episode_root: str = "episodes"
    controller_backend: str = "mock"
    settle_ms: int = 0
    motion: MotionConfig = Field(default_factory=MotionConfig)


class RandomWalkPolicyConfig(BaseModel):
    steps: int = 32
    seed: int = 7


class SquarePolicyConfig(BaseModel):
    side_repeats: int = 1
    forward_ms: int = 400
    turn_deg: int = 90


class SpinPolicyConfig(BaseModel):
    repeats: int = 8
    turn_deg: int = 45


class PolicyConfig(BaseModel):
    random_walk: RandomWalkPolicyConfig = Field(default_factory=RandomWalkPolicyConfig)
    square: SquarePolicyConfig = Field(default_factory=SquarePolicyConfig)
    spin: SpinPolicyConfig = Field(default_factory=SpinPolicyConfig)


def _load_toml(path: str | Path) -> dict:
    with Path(path).open("rb") as handle:
        return tomllib.load(handle)


def load_world_config(path: str | Path) -> WorldConfig:
    return WorldConfig.model_validate(_load_toml(path))


def load_policy_config(path: str | Path) -> PolicyConfig:
    return PolicyConfig.model_validate(_load_toml(path))
