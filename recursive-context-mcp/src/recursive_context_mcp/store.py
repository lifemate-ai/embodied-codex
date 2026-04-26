"""SQLite persistence for recursive-context-mcp."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .models import BufferRecord, ContextSession, ProgramRunRecord


class RecursiveContextStore:
    """SQLite-backed store for context sessions, buffers, and program traces."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(Path(db_path).expanduser()))
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        self._conn.close()

    def _init_db(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS context_sessions (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              description TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              state_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS context_buffers (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              name TEXT NOT NULL,
              kind TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_json TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES context_sessions(id)
            );

            CREATE TABLE IF NOT EXISTS program_runs (
              id TEXT PRIMARY KEY,
              session_id TEXT NOT NULL,
              created_at TEXT NOT NULL,
              record_json TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES context_sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_context_buffers_session
              ON context_buffers(session_id, name, kind);
            CREATE INDEX IF NOT EXISTS idx_program_runs_session
              ON program_runs(session_id, created_at);
            """
        )
        self._conn.commit()

    @staticmethod
    def _dump(model: Any) -> str:
        if hasattr(model, "model_dump"):
            return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
        return json.dumps(model, ensure_ascii=False)

    def create_session(self, session: ContextSession) -> None:
        self._conn.execute(
            """
            INSERT INTO context_sessions (id, name, description, created_at, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.name,
                session.description,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
                self._dump(session),
            ),
        )
        self._conn.commit()

    def get_session(self, session_id: str) -> ContextSession:
        row = self._conn.execute(
            "SELECT state_json FROM context_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown session_id: {session_id}")
        return ContextSession.model_validate(json.loads(row["state_json"]))

    def update_session(self, session: ContextSession) -> None:
        self._conn.execute(
            """
            UPDATE context_sessions
               SET name = ?, description = ?, updated_at = ?, state_json = ?
             WHERE id = ?
            """,
            (
                session.name,
                session.description,
                session.updated_at.isoformat(),
                self._dump(session),
                session.id,
            ),
        )
        self._conn.commit()

    def add_buffer(self, record: BufferRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO context_buffers (id, session_id, name, kind, created_at, record_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.session_id,
                record.name,
                record.kind,
                record.created_at.isoformat(),
                self._dump(record),
            ),
        )
        self._conn.commit()

    def get_buffer(self, session_id: str, buffer_id: str | None = None, name: str | None = None) -> BufferRecord:
        if buffer_id is None and name is None:
            raise ValueError("Either buffer_id or name is required")

        if buffer_id is not None:
            row = self._conn.execute(
                "SELECT record_json FROM context_buffers WHERE session_id = ? AND id = ?",
                (session_id, buffer_id),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT record_json
                  FROM context_buffers
                 WHERE session_id = ? AND name = ?
                 ORDER BY created_at DESC
                 LIMIT 1
                """,
                (session_id, name),
            ).fetchone()

        if row is None:
            raise KeyError(f"Unknown buffer in session {session_id}")
        return BufferRecord.model_validate(json.loads(row["record_json"]))

    def list_buffers(self, session_id: str, kind: str | None = None) -> list[BufferRecord]:
        if kind is None:
            rows = self._conn.execute(
                "SELECT record_json FROM context_buffers WHERE session_id = ? ORDER BY created_at ASC",
                (session_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT record_json
                  FROM context_buffers
                 WHERE session_id = ? AND kind = ?
                 ORDER BY created_at ASC
                """,
                (session_id, kind),
            ).fetchall()
        return [BufferRecord.model_validate(json.loads(row["record_json"])) for row in rows]

    def add_program_run(self, record: ProgramRunRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO program_runs (id, session_id, created_at, record_json)
            VALUES (?, ?, ?, ?)
            """,
            (record.id, record.session_id, record.created_at.isoformat(), self._dump(record)),
        )
        self._conn.commit()

    def list_program_runs(self, session_id: str) -> list[ProgramRunRecord]:
        rows = self._conn.execute(
            "SELECT record_json FROM program_runs WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [ProgramRunRecord.model_validate(json.loads(row["record_json"])) for row in rows]
