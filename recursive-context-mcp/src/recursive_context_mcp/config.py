"""Configuration for recursive-context-mcp."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXCLUDE_PATTERNS: tuple[str, ...] = (
    ".git/**",
    "**/.git/**",
    ".venv/**",
    "**/.venv/**",
    "__pycache__/**",
    "**/__pycache__/**",
    ".pytest_cache/**",
    "**/.pytest_cache/**",
    ".ruff_cache/**",
    "**/.ruff_cache/**",
    "node_modules/**",
    "**/node_modules/**",
    "dist/**",
    "**/dist/**",
    "build/**",
    "**/build/**",
)


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _tuple_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.environ.get(name)
    if value is None:
        return default
    return tuple(pattern.strip() for pattern in value.split(",") if pattern.strip())


@dataclass(frozen=True)
class RecursiveContextConfig:
    """Runtime configuration for recursive context sessions."""

    db_path: str = "~/.codex/recursive-context/recursive_context.db"
    max_read_chars: int = 20000
    max_search_file_bytes: int = 2_000_000
    enable_programs: bool = False
    exclude_patterns: tuple[str, ...] = DEFAULT_EXCLUDE_PATTERNS

    @classmethod
    def from_env(cls) -> "RecursiveContextConfig":
        return cls(
            db_path=os.environ.get("RECURSIVE_CONTEXT_DB_PATH", cls.db_path),
            max_read_chars=int(os.environ.get("RECURSIVE_CONTEXT_MAX_READ_CHARS", cls.max_read_chars)),
            max_search_file_bytes=int(
                os.environ.get("RECURSIVE_CONTEXT_MAX_SEARCH_FILE_BYTES", cls.max_search_file_bytes)
            ),
            enable_programs=_bool_env("RECURSIVE_CONTEXT_ENABLE_PROGRAMS", cls.enable_programs),
            exclude_patterns=_tuple_env("RECURSIVE_CONTEXT_EXCLUDE_PATTERNS", DEFAULT_EXCLUDE_PATTERNS),
        )

    @property
    def resolved_db_path(self) -> str:
        return str(Path(self.db_path).expanduser())
