"""Configuration for recursive-context-mcp."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class RecursiveContextConfig:
    """Runtime configuration for recursive context sessions."""

    db_path: str = "~/.codex/recursive-context/recursive_context.db"
    max_read_chars: int = 20000
    max_search_file_bytes: int = 2_000_000
    enable_programs: bool = False

    @classmethod
    def from_env(cls) -> "RecursiveContextConfig":
        return cls(
            db_path=os.environ.get("RECURSIVE_CONTEXT_DB_PATH", cls.db_path),
            max_read_chars=int(os.environ.get("RECURSIVE_CONTEXT_MAX_READ_CHARS", cls.max_read_chars)),
            max_search_file_bytes=int(
                os.environ.get("RECURSIVE_CONTEXT_MAX_SEARCH_FILE_BYTES", cls.max_search_file_bytes)
            ),
            enable_programs=_bool_env("RECURSIVE_CONTEXT_ENABLE_PROGRAMS", cls.enable_programs),
        )

    @property
    def resolved_db_path(self) -> str:
        return str(Path(self.db_path).expanduser())
