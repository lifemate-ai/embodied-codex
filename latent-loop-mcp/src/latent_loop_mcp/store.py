"""SQLite-backed persistence for latent-loop-mcp."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .fact_graph import canonical_node, canonical_relation, merge_fact_metadata
from .models import FactEdge, IterationRecord, LoopState


class LatentLoopStore:
    """SQLite persistence for loop state, iterations, and fact edges."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def close(self) -> None:
        """Close the underlying DB connection."""
        self._conn.close()

    def _init_db(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS loop_traces (
              id TEXT PRIMARY KEY,
              query TEXT NOT NULL,
              mode TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              state_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS loop_iterations (
              id TEXT PRIMARY KEY,
              loop_id TEXT NOT NULL,
              iteration INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              record_json TEXT NOT NULL,
              FOREIGN KEY(loop_id) REFERENCES loop_traces(id)
            );

            CREATE TABLE IF NOT EXISTS fact_edges (
              id TEXT PRIMARY KEY,
              subject TEXT NOT NULL,
              relation TEXT NOT NULL,
              object TEXT NOT NULL,
              subject_key TEXT NOT NULL,
              relation_key TEXT NOT NULL,
              object_key TEXT NOT NULL,
              source TEXT NOT NULL,
              source_type TEXT NOT NULL,
              confidence REAL NOT NULL,
              created_at TEXT NOT NULL,
              metadata_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_loop_iterations_loop
              ON loop_iterations(loop_id, iteration);
            CREATE INDEX IF NOT EXISTS idx_fact_subject_relation
              ON fact_edges(subject_key, relation_key);
            CREATE INDEX IF NOT EXISTS idx_fact_object_relation
              ON fact_edges(object_key, relation_key);
            """
        )
        self._conn.commit()

    @staticmethod
    def _dump(model: Any) -> str:
        if hasattr(model, "model_dump"):
            return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
        return json.dumps(model, ensure_ascii=False)

    def create_loop(self, state: LoopState) -> None:
        self._conn.execute(
            """
            INSERT INTO loop_traces (id, query, mode, created_at, updated_at, state_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                state.id,
                state.query,
                state.mode,
                state.created_at.isoformat(),
                state.updated_at.isoformat(),
                self._dump(state),
            ),
        )
        self._conn.commit()

    def get_loop(self, loop_id: str) -> LoopState:
        row = self._conn.execute(
            "SELECT state_json FROM loop_traces WHERE id = ?",
            (loop_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown loop_id: {loop_id}")
        return LoopState.model_validate(json.loads(row["state_json"]))

    def update_loop(self, state: LoopState) -> None:
        self._conn.execute(
            """
            UPDATE loop_traces
               SET query = ?, mode = ?, updated_at = ?, state_json = ?
             WHERE id = ?
            """,
            (
                state.query,
                state.mode,
                state.updated_at.isoformat(),
                self._dump(state),
                state.id,
            ),
        )
        self._conn.commit()

    def add_iteration(self, record: IterationRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO loop_iterations (id, loop_id, iteration, created_at, record_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.loop_id,
                record.iteration,
                record.created_at.isoformat(),
                self._dump(record),
            ),
        )
        self._conn.commit()

    def list_iterations(self, loop_id: str) -> list[IterationRecord]:
        rows = self._conn.execute(
            "SELECT record_json FROM loop_iterations WHERE loop_id = ? ORDER BY iteration ASC",
            (loop_id,),
        ).fetchall()
        return [IterationRecord.model_validate(json.loads(row["record_json"])) for row in rows]

    def get_iteration(self, iteration_id: str) -> IterationRecord | None:
        row = self._conn.execute(
            "SELECT record_json FROM loop_iterations WHERE id = ?",
            (iteration_id,),
        ).fetchone()
        if row is None:
            return None
        return IterationRecord.model_validate(json.loads(row["record_json"]))

    def get_latest_iteration(self, loop_id: str) -> IterationRecord | None:
        row = self._conn.execute(
            """
            SELECT record_json
              FROM loop_iterations
             WHERE loop_id = ?
             ORDER BY iteration DESC
             LIMIT 1
            """,
            (loop_id,),
        ).fetchone()
        if row is None:
            return None
        return IterationRecord.model_validate(json.loads(row["record_json"]))

    def upsert_fact(self, edge: FactEdge) -> FactEdge:
        subject_key = canonical_node(edge.subject)
        relation_key = canonical_relation(edge.relation)
        object_key = canonical_node(edge.object)
        existing_row = self._conn.execute(
            """
            SELECT * FROM fact_edges
             WHERE subject_key = ? AND relation_key = ? AND object_key = ?
             LIMIT 1
            """,
            (subject_key, relation_key, object_key),
        ).fetchone()

        if existing_row is None:
            self._conn.execute(
                """
                INSERT INTO fact_edges (
                  id, subject, relation, object,
                  subject_key, relation_key, object_key,
                  source, source_type, confidence, created_at, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.subject,
                    edge.relation,
                    edge.object,
                    subject_key,
                    relation_key,
                    object_key,
                    edge.source,
                    edge.source_type,
                    edge.confidence,
                    edge.created_at.isoformat(),
                    json.dumps(edge.metadata, ensure_ascii=False),
                ),
            )
            self._conn.commit()
            return edge

        existing = FactEdge(
            id=existing_row["id"],
            subject=existing_row["subject"],
            relation=existing_row["relation"],
            object=existing_row["object"],
            source=existing_row["source"],
            source_type=existing_row["source_type"],
            confidence=existing_row["confidence"],
            created_at=existing_row["created_at"],
            metadata=json.loads(existing_row["metadata_json"]),
        )

        merged_metadata = merge_fact_metadata(
            existing.metadata,
            edge.metadata,
            source=edge.source,
            source_type=edge.source_type,
        )
        merged_confidence = max(existing.confidence, edge.confidence)
        preferred_source = existing.source
        preferred_source_type = existing.source_type
        if existing.source_type == "inferred" and edge.source_type != "inferred":
            preferred_source = edge.source
            preferred_source_type = edge.source_type

        merged = FactEdge(
            id=existing.id,
            subject=existing.subject,
            relation=existing.relation,
            object=existing.object,
            source=preferred_source,
            source_type=preferred_source_type,
            confidence=merged_confidence,
            created_at=existing.created_at,
            metadata=merged_metadata,
        )

        self._conn.execute(
            """
            UPDATE fact_edges
               SET source = ?, source_type = ?, confidence = ?, metadata_json = ?
             WHERE id = ?
            """,
            (
                merged.source,
                merged.source_type,
                merged.confidence,
                json.dumps(merged.metadata, ensure_ascii=False),
                merged.id,
            ),
        )
        self._conn.commit()
        return merged

    def get_fact(self, fact_id: str) -> FactEdge | None:
        row = self._conn.execute("SELECT * FROM fact_edges WHERE id = ?", (fact_id,)).fetchone()
        if row is None:
            return None
        return FactEdge(
            id=row["id"],
            subject=row["subject"],
            relation=row["relation"],
            object=row["object"],
            source=row["source"],
            source_type=row["source_type"],
            confidence=row["confidence"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata_json"]),
        )

    def search_facts(
        self,
        *,
        subject: str | None = None,
        relation: str | None = None,
        object: str | None = None,
        query: str | None = None,
        limit: int = 10,
    ) -> list[FactEdge]:
        if not any([subject, relation, object, query]):
            raise ValueError("At least one of subject, relation, object, or query must be provided.")

        clauses: list[str] = []
        params: list[Any] = []
        if subject:
            clauses.append("subject_key = ?")
            params.append(canonical_node(subject))
        if relation:
            clauses.append("relation_key = ?")
            params.append(canonical_relation(relation))
        if object:
            clauses.append("object_key = ?")
            params.append(canonical_node(object))
        if query:
            clauses.append("(subject LIKE ? OR relation LIKE ? OR object LIKE ?)")
            like = f"%{query}%"
            params.extend([like, like, like])

        sql = "SELECT * FROM fact_edges WHERE " + " AND ".join(clauses)
        sql += " ORDER BY confidence DESC, created_at ASC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(sql, params).fetchall()
        return [
            FactEdge(
                id=row["id"],
                subject=row["subject"],
                relation=row["relation"],
                object=row["object"],
                source=row["source"],
                source_type=row["source_type"],
                confidence=row["confidence"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in rows
        ]

    def get_stats(self) -> dict[str, Any]:
        loop_count = self._conn.execute("SELECT COUNT(*) AS count FROM loop_traces").fetchone()["count"]
        iteration_rows = self._conn.execute(
            """
            SELECT loop_id, MAX(iteration) AS max_iteration
              FROM loop_iterations
             GROUP BY loop_id
            """
        ).fetchall()
        halt_rows = self._conn.execute("SELECT record_json FROM loop_iterations").fetchall()

        avg_iterations = (
            sum(row["max_iteration"] for row in iteration_rows) / len(iteration_rows) if iteration_rows else 0.0
        )
        halt_counts: dict[str, int] = {}
        overthinking_events = 0
        for row in halt_rows:
            record = IterationRecord.model_validate(json.loads(row["record_json"]))
            halt_counts[record.halt_decision] = halt_counts.get(record.halt_decision, 0) + 1
            if "degrading without new evidence" in record.halt_reason.lower():
                overthinking_events += 1

        return {
            "total_loops": loop_count,
            "avg_iterations": avg_iterations,
            "halt_counts": halt_counts,
            "overthinking_events": overthinking_events,
        }
