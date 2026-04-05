"""Memory operations (Phase 11: SQLite+numpy backend via store.py).

This module re-exports MemoryStore and score helpers from store.py for
backward compatibility with code that imports from memory.py.
"""

from .store import (
    EMOTION_BOOST_MAP,
    MemoryStore,
    calculate_emotion_boost,
    calculate_final_score,
    calculate_importance_boost,
    calculate_time_decay,
)

__all__ = [
    "MemoryStore",
    "EMOTION_BOOST_MAP",
    "calculate_time_decay",
    "calculate_emotion_boost",
    "calculate_importance_boost",
    "calculate_final_score",
]
