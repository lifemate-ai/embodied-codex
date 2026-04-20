"""Tests for loop state persistence."""

from __future__ import annotations

from latent_loop_mcp.models import Candidate, FactEdge, IterationRecord, LoopState
from latent_loop_mcp.store import LatentLoopStore


def test_store_persists_loop_trace_and_iterations(tmp_path):
    db_path = tmp_path / "latent_loop.db"
    store = LatentLoopStore(str(db_path))
    state = LoopState(query="Who is the spouse of the performer of Imagine?")
    store.create_loop(state)
    record = IterationRecord(
        loop_id=state.id,
        iteration=1,
        candidates=[Candidate(answer="Yoko Ono", score=1)],
        distribution={"yoko ono": 1.0},
    )
    store.add_iteration(record)
    store.upsert_fact(
        FactEdge(subject="Imagine", relation="performer", object="John Lennon", source="manual", source_type="test")
    )
    store.close()

    reopened = LatentLoopStore(str(db_path))
    try:
        loaded = reopened.get_loop(state.id)
        iterations = reopened.list_iterations(state.id)
        facts = reopened.search_facts(subject="Imagine", relation="performer")
    finally:
        reopened.close()

    assert loaded.id == state.id
    assert iterations[0].id == record.id
    assert facts[0].object == "John Lennon"
