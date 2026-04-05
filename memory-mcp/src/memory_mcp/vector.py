"""Numpy-based vector operations for memory similarity search."""

from __future__ import annotations

import numpy as np


def cosine_similarity(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between a query and a corpus of vectors.

    Args:
        query: Query vector of shape (dim,)
        corpus: Corpus matrix of shape (n, dim)

    Returns:
        Similarity scores of shape (n,), higher is more similar.
    """
    q_norm = query / (np.linalg.norm(query) + 1e-10)
    c_norm = corpus / (np.linalg.norm(corpus, axis=1, keepdims=True) + 1e-10)
    return c_norm @ q_norm


def encode_vector(vec: list[float]) -> bytes:
    """Encode a float list as numpy float32 bytes (for SQLite BLOB)."""
    return np.array(vec, dtype=np.float32).tobytes()


def decode_vector(blob: bytes) -> np.ndarray:
    """Decode numpy float32 bytes from SQLite BLOB."""
    return np.frombuffer(blob, dtype=np.float32)
