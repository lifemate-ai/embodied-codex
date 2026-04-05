"""Global-workspace inspired candidate selection."""

from __future__ import annotations

from dataclasses import dataclass

from .predictive import memory_tokens
from .types import Memory


@dataclass(frozen=True)
class WorkspaceCandidate:
    """Candidate for workspace competition."""

    memory: Memory
    relevance: float
    novelty: float
    prediction_error: float
    emotion_boost: float


def _candidate_utility(
    candidate: WorkspaceCandidate,
    redundancy_penalty: float,
    temperature: float,
) -> float:
    temp = max(0.1, min(2.0, temperature))
    utility = (
        0.45 * candidate.relevance
        + 0.2 * candidate.novelty
        + 0.2 * candidate.prediction_error
        + 0.15 * candidate.emotion_boost
        - 0.25 * redundancy_penalty
    )
    return utility / temp


def _redundancy_penalty(memory: Memory, selected: list[Memory]) -> float:
    if not selected:
        return 0.0

    target_tokens = memory_tokens(memory)
    if not target_tokens:
        return 0.0

    overlaps: list[float] = []
    for item in selected:
        item_tokens = memory_tokens(item)
        if not item_tokens:
            continue
        union = target_tokens | item_tokens
        if not union:
            continue
        overlaps.append(len(target_tokens & item_tokens) / len(union))

    if not overlaps:
        return 0.0
    return max(overlaps)


def select_workspace_candidates(
    candidates: list[WorkspaceCandidate],
    max_results: int,
    temperature: float = 0.7,
) -> list[tuple[WorkspaceCandidate, float]]:
    """Select memories through iterative winner-take-all competition."""
    if max_results <= 0 or not candidates:
        return []

    selected: list[tuple[WorkspaceCandidate, float]] = []
    chosen_memories: list[Memory] = []
    remaining = candidates.copy()

    while remaining and len(selected) < max_results:
        scored: list[tuple[WorkspaceCandidate, float]] = []
        for cand in remaining:
            penalty = _redundancy_penalty(cand.memory, chosen_memories)
            score = _candidate_utility(cand, penalty, temperature)
            scored.append((cand, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        best_cand, best_score = scored[0]
        selected.append((best_cand, best_score))
        chosen_memories.append(best_cand.memory)
        remaining = [cand for cand in remaining if cand.memory.id != best_cand.memory.id]

    return selected


def diversity_score(memories: list[Memory]) -> float:
    """Average pairwise diversity in [0, 1]."""
    if len(memories) <= 1:
        return 0.0

    pair_scores: list[float] = []
    for i, left in enumerate(memories):
        left_tokens = memory_tokens(left)
        for right in memories[i + 1 :]:
            right_tokens = memory_tokens(right)
            union = left_tokens | right_tokens
            if not union:
                pair_scores.append(0.0)
                continue
            overlap = len(left_tokens & right_tokens) / len(union)
            pair_scores.append(1.0 - overlap)

    if not pair_scores:
        return 0.0
    return sum(pair_scores) / len(pair_scores)

