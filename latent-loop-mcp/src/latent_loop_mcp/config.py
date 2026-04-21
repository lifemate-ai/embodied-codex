"""Configuration for latent-loop-mcp."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from ._behavior import load_behavior

load_dotenv()


def _bool_value(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _int_value(env_name: str, behavior: dict[str, object], key: str, default: int) -> int:
    raw = os.getenv(env_name)
    if raw is not None and raw != "":
        return int(raw)
    if key in behavior:
        return int(behavior[key])
    return default


def _float_value(env_name: str, behavior: dict[str, object], key: str, default: float) -> float:
    raw = os.getenv(env_name)
    if raw is not None and raw != "":
        return float(raw)
    if key in behavior:
        return float(behavior[key])
    return default


def _str_value(env_name: str, behavior: dict[str, object], key: str, default: str) -> str:
    raw = os.getenv(env_name)
    if raw is not None and raw != "":
        return raw
    if key in behavior and behavior[key] is not None:
        return str(behavior[key])
    return default


@dataclass(frozen=True)
class ServerConfig:
    """MCP server identity."""

    name: str = "latent-loop-mcp"
    version: str = "0.1.0"

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls(
            name=os.getenv("MCP_SERVER_NAME", "latent-loop-mcp"),
            version=os.getenv("MCP_SERVER_VERSION", "0.1.0"),
        )


@dataclass(frozen=True)
class LatentLoopConfig:
    """Runtime configuration for latent-loop-mcp."""

    db_path: str
    default_mode: str
    min_iterations: int
    max_iterations: int
    kl_threshold: float
    entropy_threshold: float
    margin_threshold: float
    novelty_threshold: float
    confidence_threshold: float
    overthinking_patience: int
    allow_halt_with_unresolved_low_priority: bool
    store_compact_traces: bool
    store_private_cot: bool
    min_fact_confidence: float
    allow_inferred_facts: bool
    prefer_atomic_facts: bool
    deduplicate_facts: bool
    max_paths: int

    @classmethod
    def from_env(cls) -> "LatentLoopConfig":
        behavior = load_behavior("latent_loop")
        default_db_path = str(Path.home() / ".codex" / "latent-loop" / "latent_loop.db")

        return cls(
            db_path=_str_value("LATENT_LOOP_DB_PATH", behavior, "db_path", default_db_path),
            default_mode=_str_value("LATENT_LOOP_DEFAULT_MODE", behavior, "default_mode", "adaptive"),
            min_iterations=_int_value("LATENT_LOOP_MIN_ITERATIONS", behavior, "min_iterations", 2),
            max_iterations=_int_value("LATENT_LOOP_MAX_ITERATIONS", behavior, "max_iterations", 8),
            kl_threshold=_float_value("LATENT_LOOP_KL_THRESHOLD", behavior, "kl_threshold", 0.03),
            entropy_threshold=_float_value(
                "LATENT_LOOP_ENTROPY_THRESHOLD", behavior, "entropy_threshold", 0.35
            ),
            margin_threshold=_float_value(
                "LATENT_LOOP_MARGIN_THRESHOLD", behavior, "margin_threshold", 0.25
            ),
            novelty_threshold=_float_value(
                "LATENT_LOOP_NOVELTY_THRESHOLD", behavior, "novelty_threshold", 0.05
            ),
            confidence_threshold=_float_value(
                "LATENT_LOOP_CONFIDENCE_THRESHOLD", behavior, "confidence_threshold", 0.72
            ),
            overthinking_patience=_int_value(
                "LATENT_LOOP_OVERTHINKING_PATIENCE", behavior, "overthinking_patience", 2
            ),
            allow_halt_with_unresolved_low_priority=_bool_value(
                os.getenv("LATENT_LOOP_ALLOW_HALT_WITH_UNRESOLVED_LOW_PRIORITY"),
                _bool_value(behavior.get("allow_halt_with_unresolved_low_priority"), True),
            ),
            store_compact_traces=_bool_value(
                os.getenv("LATENT_LOOP_STORE_COMPACT_TRACES"),
                _bool_value(behavior.get("store_compact_traces"), True),
            ),
            store_private_cot=_bool_value(
                os.getenv("LATENT_LOOP_STORE_PRIVATE_COT"),
                _bool_value(behavior.get("store_private_cot"), False),
            ),
            min_fact_confidence=_float_value(
                "LATENT_LOOP_MIN_FACT_CONFIDENCE", behavior, "min_fact_confidence", 0.5
            ),
            allow_inferred_facts=_bool_value(
                os.getenv("LATENT_LOOP_ALLOW_INFERRED_FACTS"),
                _bool_value(behavior.get("allow_inferred_facts"), True),
            ),
            prefer_atomic_facts=_bool_value(
                os.getenv("LATENT_LOOP_PREFER_ATOMIC_FACTS"),
                _bool_value(behavior.get("prefer_atomic_facts"), True),
            ),
            deduplicate_facts=_bool_value(
                os.getenv("LATENT_LOOP_DEDUPLICATE_FACTS"),
                _bool_value(behavior.get("deduplicate_facts"), True),
            ),
            max_paths=_int_value("LATENT_LOOP_MAX_PATHS", behavior, "max_paths", 10),
        )
