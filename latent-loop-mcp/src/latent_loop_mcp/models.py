"""Pydantic models for latent-loop-mcp."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

Decision = Literal["CONTINUE", "HALT", "VERIFY", "ASK_CLARIFY", "HALT_AT_BEST", "ABORT"]
LoopMode = Literal["fixed", "dynamic", "adaptive"]
SubgoalKind = Literal[
    "retrieve_fact",
    "compose_path",
    "verify_candidate",
    "resolve_reference",
    "ask_user",
    "retrieve_social_state",
    "check_boundary",
    "self_consistency",
]
SubgoalStatus = Literal["open", "done", "blocked", "deferred"]
CandidateStatus = Literal["active", "rejected", "verified", "tentative"]
FactSourceType = Literal["memory", "observation", "user", "inferred", "manual", "test", "sociality"]


def utc_now() -> datetime:
    """Return timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Candidate(BaseModel):
    """Candidate answer tracked during recurrent iterations."""

    answer: str
    score: float = Field(ge=0.0, default=0.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    fact_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    status: CandidateStatus = "active"


class FactEdge(BaseModel):
    """Reusable atomic fact edge."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    subject: str
    relation: str
    object: str
    source: str
    source_type: FactSourceType
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OpenSubgoal(BaseModel):
    """Outstanding unit of work for the loop."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    description: str
    kind: SubgoalKind = "retrieve_fact"
    priority: int = Field(default=3, ge=1, le=5)
    status: SubgoalStatus = "open"
    related_fact_ids: list[str] = Field(default_factory=list)


class LoopState(BaseModel):
    """Persisted loop state between iterations."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    mode: LoopMode = "adaptive"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    iteration: int = 0
    min_iterations: int = Field(default=2, ge=1, le=20)
    max_iterations: int = Field(default=8, ge=1, le=50)
    candidates: list[Candidate] = Field(default_factory=list)
    open_subgoals: list[OpenSubgoal] = Field(default_factory=list)
    active_fact_ids: list[str] = Field(default_factory=list)
    previous_distribution: dict[str, float] = Field(default_factory=dict)
    best_iteration_id: str | None = None
    best_iteration_score: float | None = None
    summary_state: str = ""
    user_visible_summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class IterationRecord(BaseModel):
    """Compact, inspectable record for one loop iteration."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    loop_id: str
    iteration: int
    created_at: datetime = Field(default_factory=utc_now)
    candidates: list[Candidate]
    distribution: dict[str, float]
    facts_used: list[str] = Field(default_factory=list)
    facts_added: list[str] = Field(default_factory=list)
    subgoals_opened: list[str] = Field(default_factory=list)
    subgoals_closed: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    kl_delta: float | None = None
    entropy: float | None = None
    normalized_entropy: float | None = None
    top_margin: float | None = None
    novelty: float | None = None
    candidate_jaccard_delta: float | None = None
    halt_decision: Decision = "CONTINUE"
    halt_reason: str = ""
    compact_trace: str = ""


class HaltingMetrics(BaseModel):
    """Metrics used for adaptive halting."""

    kl_delta: float
    entropy: float
    normalized_entropy: float
    top_margin: float
    novelty: float
    candidate_jaccard_delta: float


class HaltingResult(BaseModel):
    """Decision returned by halting evaluation."""

    decision: Decision
    reason: str
    metrics: HaltingMetrics
