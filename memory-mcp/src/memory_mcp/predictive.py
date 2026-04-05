"""Predictive-coding inspired scoring helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .types import Memory

TOKEN_PATTERN = re.compile(r"\w+", flags=re.UNICODE)


def tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase terms."""
    return {t.lower() for t in TOKEN_PATTERN.findall(text)}


def memory_tokens(memory: Memory) -> set[str]:
    """Extract searchable tokens from memory fields."""
    tokens = tokenize(memory.content)
    tokens.update(tokenize(memory.category))
    for tag in memory.tags:
        tokens.update(tokenize(tag))
    return tokens


def context_tokens(context: str) -> set[str]:
    """Extract searchable tokens from context."""
    return tokenize(context)


def calculate_context_relevance(context: str, memory: Memory) -> float:
    """Calculate lexical relevance score in [0, 1]."""
    ctx = context_tokens(context)
    if not ctx:
        return 0.0

    mem = memory_tokens(memory)
    if not mem:
        return 0.0

    overlap = len(ctx & mem)
    union = len(ctx | mem)
    if union == 0:
        return 0.0
    return overlap / union


def calculate_prediction_error(context: str, memory: Memory) -> float:
    """Predictive-coding style mismatch score in [0, 1]."""
    relevance = calculate_context_relevance(context, memory)
    return 1.0 - relevance


def calculate_novelty_score(memory: Memory, prediction_error: float) -> float:
    """Estimate novelty using activation history and prediction error."""
    activation_novelty = 1.0 / (1.0 + max(0, memory.activation_count))
    novelty = 0.6 * activation_novelty + 0.4 * max(0.0, min(1.0, prediction_error))
    return max(0.0, min(1.0, novelty))


def query_ambiguity_score(context: str) -> float:
    """Estimate ambiguity of a query in [0, 1]."""
    tokens = list(context_tokens(context))
    if not tokens:
        return 1.0

    token_count = len(tokens)
    unique_ratio = len(set(tokens)) / token_count

    brevity_score = 1.0 if token_count <= 2 else max(0.0, 1.0 - token_count / 10)
    repetition_score = 1.0 - unique_ratio

    ambiguity = 0.6 * brevity_score + 0.4 * repetition_score
    return max(0.0, min(1.0, ambiguity))


@dataclass(frozen=True)
class PredictiveDiagnostics:
    """Summary diagnostics for predictive scoring."""

    avg_prediction_error: float
    avg_novelty: float

