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


def test_list_context_files_skips_generated_paths(service, sample_context):
    started = service.start_session([str(sample_context)])

    result = service.list_context_files(started["session_id"])

    assert [entry["relative_path"] for entry in result["files"]] == ["data.jsonl", "image.bin", "notes.md"]


def test_search_context_skips_generated_paths(service, sample_context):
    started = service.start_session([str(sample_context)])

    result = service.search_context(started["session_id"], query="hidden balcony")

    assert result["hits"] == []


def test_empty_exclude_patterns_allow_generated_paths(unfiltered_service, sample_context):
    started = unfiltered_service.start_session([str(sample_context)])

    result = unfiltered_service.list_context_files(started["session_id"])

    paths = {entry["relative_path"] for entry in result["files"]}
    assert ".venv/ignored.txt" in paths
    assert "pkg/__pycache__/ignored.py" in paths


def test_specific_file_source_can_read_generated_path(service, sample_context):
    hidden_file = sample_context / ".venv" / "ignored.txt"
    started = service.start_session([str(hidden_file)])
    source_id = started["sources"][0]["id"]

    result = service.read_context_slice(started["session_id"], source_id=source_id)

    assert result["slice"]["text"] == "The hidden balcony dependency should be ignored."


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
