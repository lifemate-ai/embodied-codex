"""Diagnostics helpers for loop state evaluation."""

from __future__ import annotations

from collections.abc import Mapping


def novelty_score(facts_used_count: int, new_fact_count: int) -> float:
    """Approximate evidence novelty for this iteration."""
    return new_fact_count / max(1, facts_used_count + new_fact_count)


def candidate_jaccard_delta(
    current_distribution: Mapping[str, float], previous_distribution: Mapping[str, float]
) -> float:
    """Approximate candidate churn using Jaccard delta."""
    current = set(current_distribution)
    previous = set(previous_distribution)
    if not current and not previous:
        return 0.0
    return 1.0 - (len(current & previous) / len(current | previous))


def contradiction_penalty(contradictions: list[str]) -> float:
    """Penalty used when ranking best iteration."""
    return 0.5 if contradictions else 0.0


def iteration_quality_score(
    *,
    top_probability: float,
    top_margin: float,
    normalized_entropy: float,
    novelty: float,
    contradictions: list[str],
) -> float:
    """Score an iteration for best-iteration tracking."""
    return (
        top_probability
        + (0.3 * top_margin)
        - (0.3 * normalized_entropy)
        + (0.1 * novelty)
        - contradiction_penalty(contradictions)
    )
