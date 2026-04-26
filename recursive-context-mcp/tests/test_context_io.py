"""Context inspection behavior."""

from __future__ import annotations


def test_start_session_and_inspect_context(service, sample_context):
    started = service.start_session([str(sample_context)], name="balcony")

    inspected = service.inspect_context(started["session_id"])

    assert inspected["name"] == "balcony"
    assert inspected["stats"]["source_count"] == 1
    assert inspected["stats"]["file_count"] == 3
    assert inspected["stats"]["text_file_count"] == 2


def test_search_context_finds_text_hits(service, sample_context):
    started = service.start_session([str(sample_context)])

    result = service.search_context(started["session_id"], query="balcony")

    assert len(result["hits"]) == 1
    assert result["hits"][0]["relative_path"] == "notes.md"
    assert result["hits"][0]["line"] == 3


def test_read_context_slice_is_bounded(service, sample_context):
    started = service.start_session([str(sample_context)])
    source_id = started["sources"][0]["id"]

    result = service.read_context_slice(
        started["session_id"],
        source_id=source_id,
        relative_path="notes.md",
        start_line=3,
        max_lines=1,
    )

    assert result["slice"]["text"] == "The balcony looked bright today."
    assert result["slice"]["start_line"] == 3
    assert result["slice"]["end_line"] == 3
