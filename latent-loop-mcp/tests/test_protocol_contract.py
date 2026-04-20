"""Protocol contract tests for latent-loop service."""

from __future__ import annotations


def test_start_loop_returns_continue(service):
    result = service.start_loop(query="Who is the spouse of the performer of Imagine?")

    assert result["decision"] == "CONTINUE"
    assert result["iteration"] == 0
    assert result["loop_id"]


def test_commit_iteration_returns_valid_decision(service):
    loop = service.start_loop(query="Who is the spouse of the performer of Imagine?")
    result = service.commit_iteration(
        loop_id=loop["loop_id"],
        compact_trace="Added a strong candidate.",
        candidates=[{"answer": "Yoko Ono", "score": 2.0, "confidence": 0.9}],
    )

    assert result["decision"] in {"CONTINUE", "HALT", "VERIFY", "ASK_CLARIFY", "HALT_AT_BEST", "ABORT"}


def test_finalize_loop_uses_best_iteration_not_latest(service):
    loop = service.start_loop(query="Who is the spouse of the performer of Imagine?")
    service.commit_iteration(
        loop_id=loop["loop_id"],
        compact_trace="Strong first answer.",
        candidates=[{"answer": "Yoko Ono", "score": 5.0, "confidence": 0.9}],
    )
    service.commit_iteration(
        loop_id=loop["loop_id"],
        compact_trace="Degraded later answer.",
        candidates=[{"answer": "Maybe Paul McCartney", "score": 1.0, "confidence": 0.2}],
    )

    finalized = service.finalize_loop(loop_id=loop["loop_id"])

    assert finalized["answer"] == "Yoko Ono"


def test_get_loop_trace_does_not_include_private_chain_of_thought(service):
    loop = service.start_loop(query="test")
    service.commit_iteration(
        loop_id=loop["loop_id"],
        compact_trace="public compact summary",
        candidates=[{"answer": "A", "score": 1.0}],
    )

    trace = service.get_loop_trace(loop_id=loop["loop_id"], include_iterations=True)
    dumped = str(trace)

    assert "private_chain_of_thought" not in dumped
    assert "compact_trace" in dumped
