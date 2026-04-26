"""Trace privacy contract."""

from __future__ import annotations


def test_trace_contains_buffers_but_no_private_chain_of_thought(service, sample_context):
    started = service.start_session([str(sample_context)])
    service.commit_buffer(started["session_id"], name="summary", content="Public compact summary.")

    trace = service.get_session_trace(started["session_id"])
    dumped = str(trace)

    assert "Public compact summary" in dumped
    assert "private_chain_of_thought" in dumped
    assert "raw hidden reasoning" not in dumped
