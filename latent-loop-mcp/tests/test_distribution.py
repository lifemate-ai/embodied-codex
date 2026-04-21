"""Tests for candidate distribution helpers."""

from __future__ import annotations

from latent_loop_mcp.distribution import (
    distribution_from_candidates,
    kl_divergence,
    normalized_entropy,
    top_margin,
)
from latent_loop_mcp.models import Candidate


def test_all_zero_scores_become_uniform_distribution():
    distribution = distribution_from_candidates(
        [Candidate(answer="A", score=0), Candidate(answer="B", score=0)]
    )

    assert distribution["a"] == distribution["b"]


def test_one_candidate_has_zero_entropy_and_full_margin():
    distribution = distribution_from_candidates([Candidate(answer="Only", score=3)])

    assert normalized_entropy(distribution) == 0.0
    assert top_margin(distribution) == 1.0


def test_duplicate_canonical_answers_merge():
    distribution = distribution_from_candidates(
        [
            Candidate(answer="Yoko Ono", score=1),
            Candidate(answer="  yoko   ono ", score=2),
            Candidate(answer="John Lennon", score=1),
        ]
    )

    assert set(distribution) == {"yoko ono", "john lennon"}
    assert distribution["yoko ono"] > distribution["john lennon"]


def test_kl_is_near_zero_for_identical_distributions():
    distribution = distribution_from_candidates([Candidate(answer="A", score=2), Candidate(answer="B", score=1)])

    assert kl_divergence(distribution, distribution) < 1e-6


def test_kl_increases_when_distribution_changes():
    previous = distribution_from_candidates([Candidate(answer="A", score=10), Candidate(answer="B", score=1)])
    current = distribution_from_candidates([Candidate(answer="A", score=1), Candidate(answer="B", score=10)])

    assert kl_divergence(current, previous) > 0.5
