"""Optional program execution behavior."""

from __future__ import annotations


def test_run_program_is_disabled_by_default(service, sample_context):
    started = service.start_session([str(sample_context)])

    result = service.run_program(started["session_id"], "result = ctx.stats()")

    assert result["enabled"] is False
    assert "disabled" in result["run"]["error"]


def test_run_program_can_use_context_api_when_enabled(program_service, sample_context):
    started = program_service.start_session([str(sample_context)])

    result = program_service.run_program(
        started["session_id"],
        "hits = ctx.search('bright')\nresult = {'hit_count': len(hits), 'first': hits[0]['relative_path']}",
    )

    assert result["enabled"] is True
    assert result["run"]["error"] == ""
    assert result["run"]["result"]["hit_count"] == 2
    assert result["run"]["result"]["first"] in {"data.jsonl", "notes.md"}


def test_run_program_rejects_imports(program_service, sample_context):
    started = program_service.start_session([str(sample_context)])

    result = program_service.run_program(started["session_id"], "import os\nresult = os.getcwd()")

    assert result["run"]["error"]
    assert "Unsupported program node" in result["run"]["error"]
