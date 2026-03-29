"""Pytest fixtures for Memory MCP tests."""

from pathlib import Path

import pytest
import pytest_asyncio

from memory_mcp.config import MemoryConfig
from memory_mcp.store import MemoryStore


@pytest.fixture
def temp_db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite database path."""
    return str(tmp_path / "test_memory.db")


@pytest.fixture
def memory_config(temp_db_path: str) -> MemoryConfig:
    """Create test memory config."""
    return MemoryConfig(
        db_path=temp_db_path,
        collection_name="test_memories",
    )


@pytest_asyncio.fixture
async def memory_store(memory_config: MemoryConfig) -> MemoryStore:
    """Create and connect a memory store."""
    store = MemoryStore(memory_config)
    await store.connect()
    yield store
    await store.disconnect()
