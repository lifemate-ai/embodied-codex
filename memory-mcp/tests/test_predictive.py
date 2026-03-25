"""Tests for predictive-coding inspired helpers."""

from memory_mcp.predictive import (
    calculate_context_relevance,
    calculate_novelty_score,
    calculate_prediction_error,
    query_ambiguity_score,
)
from memory_mcp.types import Memory


def _memory(content: str, activation_count: int = 0) -> Memory:
    return Memory(
        id="m1",
        content=content,
        timestamp="2026-02-07T00:00:00",
        emotion="neutral",
        importance=3,
        category="daily",
        activation_count=activation_count,
    )


def test_prediction_error_is_lower_for_matching_context():
    memory = _memory("camera sees morning sky from window")
    good_context = "morning sky camera"
    bad_context = "database migration schema"

    good_error = calculate_prediction_error(good_context, memory)
    bad_error = calculate_prediction_error(bad_context, memory)

    assert good_error < bad_error


def test_context_relevance_is_normalized():
    memory = _memory("camera sky")
    relevance = calculate_context_relevance("camera sky", memory)
    assert 0.0 <= relevance <= 1.0
    assert relevance > 0.0


def test_novelty_decreases_with_activation_count():
    memory_fresh = _memory("new observation", activation_count=0)
    memory_replayed = _memory("new observation", activation_count=10)

    novelty_fresh = calculate_novelty_score(memory_fresh, prediction_error=0.5)
    novelty_replayed = calculate_novelty_score(memory_replayed, prediction_error=0.5)

    assert novelty_fresh > novelty_replayed


def test_query_ambiguity_prefers_short_queries():
    short_query = "camera"
    long_query = "camera morning sky balcony cloud and sunlight details"

    short_score = query_ambiguity_score(short_query)
    long_score = query_ambiguity_score(long_query)

    assert short_score > long_score
    assert 0.0 <= short_score <= 1.0
