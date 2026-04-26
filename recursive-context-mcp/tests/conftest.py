"""Test fixtures for recursive-context-mcp."""

from __future__ import annotations

import pytest

from recursive_context_mcp.config import RecursiveContextConfig
from recursive_context_mcp.service import RecursiveContextService
from recursive_context_mcp.store import RecursiveContextStore


@pytest.fixture
def sample_context(tmp_path):
    root = tmp_path / "context"
    root.mkdir()
    (root / "notes.md").write_text(
        "# Outside observation\n\nThe balcony looked bright today.\nThe same street was quiet yesterday.\n",
        encoding="utf-8",
    )
    (root / "data.jsonl").write_text(
        '{"day":"2026-04-26","impression":"bright"}\n'
        '{"day":"2026-04-25","impression":"quiet"}\n',
        encoding="utf-8",
    )
    (root / "image.bin").write_bytes(b"\x00\x01\x02")
    return root


@pytest.fixture
def service(tmp_path):
    store = RecursiveContextStore(str(tmp_path / "recursive_context.db"))
    svc = RecursiveContextService(store, RecursiveContextConfig(db_path=str(tmp_path / "recursive_context.db")))
    try:
        yield svc
    finally:
        store.close()


@pytest.fixture
def program_service(tmp_path):
    store = RecursiveContextStore(str(tmp_path / "recursive_context.db"))
    svc = RecursiveContextService(
        store,
        RecursiveContextConfig(db_path=str(tmp_path / "recursive_context.db"), enable_programs=True),
    )
    try:
        yield svc
    finally:
        store.close()
