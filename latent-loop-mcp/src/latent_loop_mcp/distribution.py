"""Candidate distribution helpers for latent-loop-mcp."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import log

from .models import Candidate

EPSILON = 1e-9


def canonical_answer(answer: str) -> str:
    """Normalize candidate answer text for distribution accounting."""
    return " ".join(answer.strip().lower().split())


def merge_candidate_scores(candidates: Sequence[Candidate]) -> dict[str, float]:
    """Merge duplicate candidates by canonical answer."""
    merged: dict[str, float] = {}
    for candidate in candidates:
        key = canonical_answer(candidate.answer)
        merged[key] = merged.get(key, 0.0) + candidate.score
    return merged


def normalize_scores(scores: Mapping[str, float]) -> dict[str, float]:
    """Normalize arbitrary non-negative scores into a probability distribution."""
    if not scores:
        return {}

    total = sum(max(value, 0.0) + EPSILON for value in scores.values())
    if total <= 0:
        uniform = 1.0 / len(scores)
        return {key: uniform for key in scores}
    return {key: (max(value, 0.0) + EPSILON) / total for key, value in scores.items()}


def distribution_from_candidates(candidates: Sequence[Candidate]) -> dict[str, float]:
    """Build normalized candidate distribution."""
    return normalize_scores(merge_candidate_scores(candidates))


def representative_candidates(candidates: Sequence[Candidate]) -> dict[str, Candidate]:
    """Choose one representative candidate for each canonical answer."""
    result: dict[str, Candidate] = {}
    for candidate in candidates:
        key = canonical_answer(candidate.answer)
        current = result.get(key)
        if current is None:
            result[key] = candidate
            continue
        if (candidate.score, candidate.confidence or 0.0) > (current.score, current.confidence or 0.0):
            result[key] = candidate
    return result


def entropy(distribution: Mapping[str, float]) -> float:
    """Shannon entropy."""
    total = 0.0
    for probability in distribution.values():
        if probability <= 0.0:
            continue
        total -= probability * log(probability)
    return total


def normalized_entropy(distribution: Mapping[str, float]) -> float:
    """Entropy normalized to [0, 1]."""
    if len(distribution) <= 1:
        return 0.0
    return entropy(distribution) / log(len(distribution))


def kl_divergence(current: Mapping[str, float], previous: Mapping[str, float]) -> float:
    """KL(current || previous) on smoothed union support."""
    if not current:
        return 0.0
    support = set(current) | set(previous)
    total = 0.0
    for key in support:
        p_cur = current.get(key, 0.0) + EPSILON
        p_prev = previous.get(key, 0.0) + EPSILON
        total += p_cur * log(p_cur / p_prev)
    return total


def top_margin(distribution: Mapping[str, float]) -> float:
    """Difference between the top two probabilities."""
    if not distribution:
        return 0.0
    values = sorted(distribution.values(), reverse=True)
    if len(values) == 1:
        return 1.0
    return values[0] - values[1]


def top_candidate_key(distribution: Mapping[str, float]) -> str | None:
    """Return canonical key of the top candidate."""
    if not distribution:
        return None
    return max(distribution, key=distribution.get)
