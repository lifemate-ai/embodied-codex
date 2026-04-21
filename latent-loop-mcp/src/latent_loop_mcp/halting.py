"""Adaptive halting logic for latent-loop-mcp."""

from __future__ import annotations

from .config import LatentLoopConfig
from .models import HaltingMetrics, HaltingResult, LoopState


def _top_candidate_confidence(state: LoopState, top_probability: float) -> float:
    if not state.candidates:
        return top_probability
    top_confidence = max(
        (candidate.confidence for candidate in state.candidates if candidate.confidence is not None),
        default=None,
    )
    return top_probability if top_confidence is None else top_confidence


def _has_high_priority_unresolved_subgoals(state: LoopState) -> bool:
    return any(subgoal.status == "open" and subgoal.priority <= 2 for subgoal in state.open_subgoals)


def _has_ask_user_subgoal(state: LoopState) -> bool:
    return any(subgoal.status == "open" and subgoal.kind == "ask_user" for subgoal in state.open_subgoals)


def _detect_overthinking(state: LoopState, config: LatentLoopConfig) -> bool:
    margin_history = list(state.metadata.get("margin_history", []))
    novelty_history = list(state.metadata.get("novelty_history", []))
    patience = config.overthinking_patience
    if len(margin_history) < patience + 1 or len(novelty_history) < patience:
        return False

    recent_margins = margin_history[-(patience + 1) :]
    recent_novelties = novelty_history[-patience:]
    decreasing = all(earlier > later for earlier, later in zip(recent_margins, recent_margins[1:]))
    no_novelty = all(value <= config.novelty_threshold for value in recent_novelties)
    return decreasing and no_novelty


def evaluate_halting(
    state: LoopState,
    metrics: HaltingMetrics,
    *,
    top_probability: float,
    contradictions: list[str],
    config: LatentLoopConfig,
) -> HaltingResult:
    """Evaluate adaptive halting decision for the current iteration."""
    confidence = _top_candidate_confidence(state, top_probability)

    if state.iteration < state.min_iterations:
        return HaltingResult(decision="CONTINUE", reason="Minimum iteration budget not reached.", metrics=metrics)

    if not state.candidates:
        if _has_ask_user_subgoal(state):
            return HaltingResult(
                decision="ASK_CLARIFY",
                reason="No viable candidates and a clarification subgoal remains open.",
                metrics=metrics,
            )
        return HaltingResult(
            decision="CONTINUE",
            reason="No viable candidates yet; continue retrieval/composition.",
            metrics=metrics,
        )

    if contradictions:
        return HaltingResult(
            decision="VERIFY",
            reason="Contradictions detected; run a verification-focused iteration.",
            metrics=metrics,
        )

    if _has_high_priority_unresolved_subgoals(state):
        return HaltingResult(
            decision="VERIFY",
            reason="High-priority subgoals remain unresolved.",
            metrics=metrics,
        )

    if (
        metrics.kl_delta < config.kl_threshold
        and metrics.normalized_entropy < config.entropy_threshold
        and metrics.top_margin > config.margin_threshold
        and confidence >= config.confidence_threshold
    ):
        return HaltingResult(
            decision="HALT",
            reason="Distribution stabilized with low entropy and sufficient margin.",
            metrics=metrics,
        )

    if _detect_overthinking(state, config):
        return HaltingResult(
            decision="HALT_AT_BEST",
            reason="Later iterations are degrading without new evidence.",
            metrics=metrics,
        )

    if state.iteration >= state.max_iterations:
        return HaltingResult(
            decision="HALT_AT_BEST",
            reason="Reached maximum iteration budget.",
            metrics=metrics,
        )

    return HaltingResult(
        decision="CONTINUE",
        reason="Keep iterating; uncertainty or unresolved work remains.",
        metrics=metrics,
    )
