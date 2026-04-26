"""Buffer and sub-query packet behavior."""

from __future__ import annotations


def test_commit_and_get_buffer(service, sample_context):
    started = service.start_session([str(sample_context)])

    committed = service.commit_buffer(
        started["session_id"],
        name="observation-summary",
        content="The context contains balcony observation notes.",
        kind="note",
    )
    loaded = service.get_buffer(started["session_id"], buffer_id=committed["buffer"]["id"])

    assert loaded["buffer"]["content"] == "The context contains balcony observation notes."


def test_prepare_sub_query_packages_slices_and_buffers(service, sample_context):
    started = service.start_session([str(sample_context)])
    source_id = started["sources"][0]["id"]
    service.commit_buffer(
        started["session_id"],
        name="task-note",
        content="Focus on change detection.",
    )

    packet = service.prepare_sub_query(
        started["session_id"],
        prompt="Summarize the scene change.",
        slice_refs=[
            {
                "source_id": source_id,
                "relative_path": "notes.md",
                "start_line": 3,
                "max_lines": 2,
            }
        ],
        buffer_names=["task-note"],
        name="change-subquery",
    )

    assert packet["sub_query_buffer_id"]
    assert packet["packet"]["prompt"] == "Summarize the scene change."
    assert "balcony" in packet["packet"]["slices"][0]["text"]
    assert packet["packet"]["buffers"][0]["name"] == "task-note"


def test_record_sub_result_requires_existing_packet(service, sample_context):
    started = service.start_session([str(sample_context)])
    packet = service.prepare_sub_query(started["session_id"], prompt="Inspect this.")

    result = service.record_sub_result(
        started["session_id"],
        sub_query_buffer_id=packet["sub_query_buffer_id"],
        content="The relevant change is brightness.",
    )

    assert result["buffer"]["kind"] == "sub_result"
    assert result["buffer"]["metadata"]["sub_query_buffer_id"] == packet["sub_query_buffer_id"]
