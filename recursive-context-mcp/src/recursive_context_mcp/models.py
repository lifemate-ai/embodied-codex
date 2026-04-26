"""Data models for recursive-context-mcp."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


SourceKind = Literal["file", "directory"]
BufferKind = Literal["note", "manifest", "sub_query", "sub_result", "program_result", "final"]


class ContextSource(BaseModel):
    id: str = Field(default_factory=lambda: new_id("src"))
    uri: str
    path: str
    kind: SourceKind
    label: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ContextSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ctx"))
    name: str = ""
    description: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    sources: list[ContextSource] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class FileEntry(BaseModel):
    source_id: str
    relative_path: str
    path: str
    size_bytes: int
    is_text: bool


class SearchHit(BaseModel):
    source_id: str
    relative_path: str
    line: int
    text: str


class ContextSlice(BaseModel):
    source_id: str
    relative_path: str
    start_line: int
    end_line: int
    text: str
    truncated: bool = False


class BufferRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("buf"))
    session_id: str
    name: str
    kind: BufferKind = "note"
    content: str
    created_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProgramRunRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    session_id: str
    code: str
    result: Any = None
    stdout: str = ""
    error: str = ""
    created_at: datetime = Field(default_factory=now_utc)
    metadata: dict[str, Any] = Field(default_factory=dict)
