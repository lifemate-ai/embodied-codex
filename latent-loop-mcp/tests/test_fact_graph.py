"""Tests for fact graph helpers."""

from __future__ import annotations

from latent_loop_mcp.fact_graph import compose_path
from latent_loop_mcp.models import FactEdge


def test_upsert_deduplicates_facts(store):
    first = store.upsert_fact(
        FactEdge(subject="John Lennon", relation="spouse", object="Yoko Ono", source="memory:1", source_type="memory")
    )
    second = store.upsert_fact(
        FactEdge(
            subject=" john  lennon ",
            relation="spouse",
            object="Yoko Ono",
            source="memory:2",
            source_type="memory",
        )
    )

    assert first.id == second.id


def test_compose_two_hop_path(store):
    store.upsert_fact(
        FactEdge(subject="Imagine", relation="performer", object="John Lennon", source="manual", source_type="test")
    )
    store.upsert_fact(
        FactEdge(subject="John Lennon", relation="spouse", object="Yoko Ono", source="manual", source_type="test")
    )

    paths = compose_path(store, start="Imagine", relations=["performer", "spouse"])

    assert paths[0]["entities"] == ["Imagine", "John Lennon", "Yoko Ono"]


def test_compose_six_hop_path(store):
    for index in range(6):
        store.upsert_fact(
            FactEdge(
                subject=f"e{index}",
                relation=f"r{index}",
                object=f"e{index + 1}",
                source="manual",
                source_type="test",
            )
        )

    paths = compose_path(store, start="e0", relations=[f"r{index}" for index in range(6)])

    assert paths[0]["entities"][-1] == "e6"


def test_confidence_multiplies_along_path(store):
    store.upsert_fact(
        FactEdge(subject="A", relation="r1", object="B", source="manual", source_type="test", confidence=0.8)
    )
    store.upsert_fact(
        FactEdge(subject="B", relation="r2", object="C", source="manual", source_type="test", confidence=0.5)
    )

    paths = compose_path(store, start="A", relations=["r1", "r2"], min_confidence=0.0)

    assert paths[0]["confidence"] == 0.4


def test_no_path_returns_empty_result(store):
    assert compose_path(store, start="A", relations=["missing"]) == []


def test_inferred_facts_do_not_override_atomic_facts(store):
    atomic = store.upsert_fact(
        FactEdge(subject="A", relation="kind", object="cat", source="manual", source_type="manual", confidence=0.6)
    )
    merged = store.upsert_fact(
        FactEdge(subject="A", relation="kind", object="cat", source="guess", source_type="inferred", confidence=0.9)
    )

    assert merged.id == atomic.id
    assert merged.source_type == "manual"
