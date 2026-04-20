"""Fixtures for latent-loop-mcp tests."""

from __future__ import annotations

import pytest

from latent_loop_mcp.config import LatentLoopConfig
from latent_loop_mcp.service import LatentLoopService
from latent_loop_mcp.store import LatentLoopStore


@pytest.fixture
def loop_config(tmp_path):
    return LatentLoopConfig(
        db_path=str(tmp_path / "latent_loop.db"),
        default_mode="adaptive",
        min_iterations=2,
        max_iterations=8,
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


@pytest.fixture
def store(loop_config):
    instance = LatentLoopStore(loop_config.db_path)
    try:
        yield instance
    finally:
        instance.close()


@pytest.fixture
def service(loop_config, store):
    return LatentLoopService(loop_config, store)
