"""Tests for adaptive halting decisions."""

from __future__ import annotations

from latent_loop_mcp.config import LatentLoopConfig
from latent_loop_mcp.halting import evaluate_halting
from latent_loop_mcp.models import Candidate, HaltingMetrics, LoopState, OpenSubgoal


def _config() -> LatentLoopConfig:
    return LatentLoopConfig(
        db_path="/tmp/latent-loop-test.db",
        default_mode="adaptive",
        min_iterations=2,
        max_iterations=4,
        kl_threshold=0.03,
        entropy_threshold=0.35,
        margin_threshold=0.25,
        novelty_threshold=0.05,
        confidence_threshold=0.72,
        overthinking_patience=2,
        allow_halt_with_unresolved_low_priority=True,
        store_compact_traces=True,
        store_private_cot=False,
        min_fact_confidence=0.5,
        allow_inferred_facts=True,
        prefer_atomic_facts=True,
        deduplicate_facts=True,
        max_paths=10,
    )


def _metrics(kl: float, norm_entropy: float, margin: float, novelty: float = 0.0) -> HaltingMetrics:
    return HaltingMetrics(
        kl_delta=kl,
        entropy=norm_entropy,
        normalized_entropy=norm_entropy,
        top_margin=margin,
        novelty=novelty,
        candidate_jaccard_delta=0.0,
    )


def test_does_not_halt_before_min_iterations():
    state = LoopState(iteration=1, query="test", candidates=[Candidate(answer="A", score=1, confidence=0.9)])

    result = evaluate_halting(
        state,
        _metrics(0.0, 0.0, 0.8),
        top_probability=1.0,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "CONTINUE"


def test_halts_when_stable_and_confident():
    state = LoopState(iteration=2, query="test", candidates=[Candidate(answer="A", score=3, confidence=0.9)])

    result = evaluate_halting(
        state,
        _metrics(0.01, 0.2, 0.6),
        top_probability=0.9,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "HALT"


def test_does_not_halt_when_entropy_is_high():
    state = LoopState(
        iteration=2,
        query="test",
        candidates=[Candidate(answer="A", score=2, confidence=0.9), Candidate(answer="B", score=2, confidence=0.9)],
    )

    result = evaluate_halting(
        state,
        _metrics(0.01, 0.8, 0.1),
        top_probability=0.5,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "CONTINUE"


def test_high_priority_subgoals_force_verify():
    state = LoopState(
        iteration=2,
        query="test",
        candidates=[Candidate(answer="A", score=3, confidence=0.95)],
        open_subgoals=[OpenSubgoal(description="Need one more fact", priority=1)],
    )

    result = evaluate_halting(
        state,
        _metrics(0.01, 0.1, 0.8),
        top_probability=0.9,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "VERIFY"


def test_max_iterations_returns_halt_at_best():
    state = LoopState(
        iteration=4,
        query="test",
        max_iterations=4,
        candidates=[Candidate(answer="A", score=3, confidence=0.6)],
    )

    result = evaluate_halting(
        state,
        _metrics(0.2, 0.5, 0.1),
        top_probability=0.6,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "HALT_AT_BEST"


def test_overthinking_returns_halt_at_best():
    state = LoopState(
        iteration=3,
        query="test",
        candidates=[Candidate(answer="A", score=3, confidence=0.8)],
        metadata={"margin_history": [0.8, 0.5, 0.2], "novelty_history": [0.0, 0.0, 0.0]},
    )

    result = evaluate_halting(
        state,
        _metrics(0.2, 0.4, 0.2, novelty=0.0),
        top_probability=0.8,
        contradictions=[],
        config=_config(),
    )

    assert result.decision == "HALT_AT_BEST"
