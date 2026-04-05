#!/usr/bin/env python3
"""ChromaDB → SQLite+numpy migration script.

Usage:
    uv run python scripts/migrate_chroma_to_sqlite.py \
        --source ~/.codex/memories/chroma \
        --dest ~/.codex/memories/memory.db

What it does:
    1. Read all memories + embeddings from ChromaDB collection
    2. Insert into SQLite memories + embeddings tables
    3. Expand coactivation JSON → coactivation table
    4. Migrate episodes collection → episodes table
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def _ddl(conn: sqlite3.Connection) -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        content TEXT NOT NULL,
        normalized_content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        emotion TEXT NOT NULL DEFAULT 'neutral',
        importance INTEGER NOT NULL DEFAULT 3,
        category TEXT NOT NULL DEFAULT 'daily',
        access_count INTEGER NOT NULL DEFAULT 0,
        last_accessed TEXT NOT NULL DEFAULT '',
        linked_ids TEXT NOT NULL DEFAULT '',
        episode_id TEXT,
        sensory_data TEXT NOT NULL DEFAULT '',
        camera_position TEXT,
        tags TEXT NOT NULL DEFAULT '',
        links TEXT NOT NULL DEFAULT '',
        novelty_score REAL NOT NULL DEFAULT 0.0,
        prediction_error REAL NOT NULL DEFAULT 0.0,
        activation_count INTEGER NOT NULL DEFAULT 0,
        last_activated TEXT NOT NULL DEFAULT '',
        reading TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_memories_emotion    ON memories(emotion);
    CREATE INDEX IF NOT EXISTS idx_memories_category   ON memories(category);
    CREATE INDEX IF NOT EXISTS idx_memories_timestamp  ON memories(timestamp);
    CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance);

    CREATE TABLE IF NOT EXISTS embeddings (
        memory_id TEXT PRIMARY KEY REFERENCES memories(id) ON DELETE CASCADE,
        vector BLOB NOT NULL
    );

    CREATE TABLE IF NOT EXISTS coactivation (
        source_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        target_id TEXT NOT NULL REFERENCES memories(id) ON DELETE CASCADE,
        weight REAL NOT NULL CHECK(weight >= 0.0 AND weight <= 1.0),
        PRIMARY KEY (source_id, target_id)
    );
    CREATE INDEX IF NOT EXISTS idx_coactivation_source ON coactivation(source_id);
    CREATE INDEX IF NOT EXISTS idx_coactivation_target ON coactivation(target_id);

    CREATE TABLE IF NOT EXISTS episodes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT,
        memory_ids TEXT NOT NULL DEFAULT '',
        participants TEXT NOT NULL DEFAULT '',
        location_context TEXT,
        summary TEXT NOT NULL DEFAULT '',
        emotion TEXT NOT NULL DEFAULT 'neutral',
        importance INTEGER NOT NULL DEFAULT 3
    );
    """
    for stmt in ddl.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)
    conn.commit()


def migrate(source: str, dest: str) -> None:
    try:
        import chromadb
        import numpy as np
    except ImportError as e:
        print(f"Error: {e}")
        print("Install chromadb and numpy: uv add chromadb numpy")
        sys.exit(1)

    source_path = Path(source).expanduser()
    dest_path = Path(dest).expanduser()

    if not source_path.exists():
        print(f"Error: source path does not exist: {source_path}")
        sys.exit(1)

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Source: {source_path}")
    print(f"Dest:   {dest_path}")
    print()

    # Connect to ChromaDB
    client = chromadb.PersistentClient(path=str(source_path))

    collections = client.list_collections()
    print(f"Collections found: {[c.name for c in collections]}")
    print()

    # Prompt
    answer = input("Proceed with migration? [y/N] ").strip().lower()
    if answer != "y":
        print("Aborted.")
        sys.exit(0)

    # Open SQLite
    conn = sqlite3.connect(str(dest_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    _ddl(conn)

    memory_ids_in_dest: set[str] = set()

    # ── Migrate memories collection ────────────────────
    collection_names = [c.name for c in collections]
    memories_collection_name = next(
        (n for n in collection_names if n != "episodes"), None
    )
    if memories_collection_name:
        coll = client.get_collection(memories_collection_name)
        result = coll.get(include=["embeddings", "documents", "metadatas"])
        ids = result.get("ids") or []
        embeddings_raw = result.get("embeddings")
        embeddings = embeddings_raw if embeddings_raw is not None else []
        documents_raw = result.get("documents")
        documents = documents_raw if documents_raw is not None else []
        metadatas_raw = result.get("metadatas")
        metadatas = metadatas_raw if metadatas_raw is not None else []

        print(f"Migrating {len(ids)} memories from '{memories_collection_name}'...")

        coactivation_entries: list[tuple[str, str, float]] = []

        for i, memory_id in enumerate(ids):
            meta = dict(metadatas[i]) if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""
            emb = embeddings[i] if i < len(embeddings) else None

            # Extract coactivation before insert
            coact_raw = meta.pop("coactivation", "") or ""
            if coact_raw:
                try:
                    coact_dict = json.loads(coact_raw) if isinstance(coact_raw, str) else coact_raw
                    if isinstance(coact_dict, dict):
                        for target_id, weight in coact_dict.items():
                            try:
                                w = float(weight)
                                w = max(0.0, min(1.0, w))
                                coactivation_entries.append((memory_id, target_id, w))
                            except (TypeError, ValueError):
                                pass
                except (json.JSONDecodeError, TypeError):
                    pass

            # original content is in metadata["content"] (Phase 8+)
            original_content = meta.get("content") or doc
            episode_id = meta.get("episode_id") or None
            if episode_id == "":
                episode_id = None

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO memories (
                        id, content, normalized_content, timestamp,
                        emotion, importance, category, access_count, last_accessed,
                        linked_ids, episode_id, sensory_data, camera_position,
                        tags, links, novelty_score, prediction_error,
                        activation_count, last_activated, reading
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        memory_id,
                        original_content,
                        doc,  # normalized_content (was stored as document in ChromaDB)
                        meta.get("timestamp", ""),
                        meta.get("emotion", "neutral"),
                        int(meta.get("importance", 3)),
                        meta.get("category", "daily"),
                        int(meta.get("access_count", 0)),
                        meta.get("last_accessed", ""),
                        meta.get("linked_ids", ""),
                        episode_id,
                        meta.get("sensory_data", ""),
                        meta.get("camera_position") or None,
                        meta.get("tags", ""),
                        meta.get("links", ""),
                        float(meta.get("novelty_score", 0.0)),
                        float(meta.get("prediction_error", 0.0)),
                        int(meta.get("activation_count", 0)),
                        meta.get("last_activated", ""),
                        meta.get("reading") or None,
                    ),
                )
                memory_ids_in_dest.add(memory_id)
            except Exception as e:
                print(f"  Warning: failed to insert memory {memory_id}: {e}")
                continue

            if emb is not None:
                vec_bytes = np.array(emb, dtype=np.float32).tobytes()
                conn.execute(
                    "INSERT OR IGNORE INTO embeddings (memory_id, vector) VALUES (?,?)",
                    (memory_id, vec_bytes),
                )

        conn.commit()
        print(f"  Inserted {len(memory_ids_in_dest)} memories.")

        # Insert coactivation (only where both sides exist)
        coa_inserted = 0
        for source_id, target_id, weight in coactivation_entries:
            if source_id in memory_ids_in_dest and target_id in memory_ids_in_dest:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO coactivation (source_id, target_id, weight)
                           VALUES (?,?,?)""",
                        (source_id, target_id, weight),
                    )
                    coa_inserted += 1
                except Exception:
                    pass
        conn.commit()
        print(f"  Inserted {coa_inserted} coactivation weights.")

    # ── Migrate episodes collection ────────────────────
    if "episodes" in collection_names:
        ep_coll = client.get_collection("episodes")
        ep_result = ep_coll.get(include=["documents", "metadatas"])
        ep_ids = ep_result.get("ids") or []
        ep_docs = ep_result.get("documents") or []
        ep_metas = ep_result.get("metadatas") or []

        print(f"\nMigrating {len(ep_ids)} episodes...")
        ep_inserted = 0
        for i, ep_id in enumerate(ep_ids):
            meta = dict(ep_metas[i]) if i < len(ep_metas) else {}
            summary = ep_docs[i] if i < len(ep_docs) else ""
            end_time = meta.get("end_time") or None
            if end_time == "":
                end_time = None
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO episodes
                       (id, title, start_time, end_time, memory_ids, participants,
                        location_context, summary, emotion, importance)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    (
                        ep_id,
                        meta.get("title", ""),
                        meta.get("start_time", ""),
                        end_time,
                        meta.get("memory_ids", ""),
                        meta.get("participants", ""),
                        meta.get("location_context") or None,
                        summary,
                        meta.get("emotion", "neutral"),
                        int(meta.get("importance", 3)),
                    ),
                )
                ep_inserted += 1
            except Exception as e:
                print(f"  Warning: failed to insert episode {ep_id}: {e}")
        conn.commit()
        print(f"  Inserted {ep_inserted} episodes.")

    conn.close()
    print("\nMigration complete!")
    print(f"SQLite database: {dest_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate ChromaDB memories to SQLite+numpy")
    parser.add_argument(
        "--source",
        default=str(Path.home() / ".claude" / "memories" / "chroma"),
        help="Path to ChromaDB directory (default: ~/.claude/memories/chroma)",
    )
    parser.add_argument(
        "--dest",
        default=str(Path.home() / ".claude" / "memories" / "memory.db"),
        help="Path to SQLite output file (default: ~/.claude/memories/memory.db)",
    )
    args = parser.parse_args()
    migrate(source=args.source, dest=args.dest)


if __name__ == "__main__":
    main()
