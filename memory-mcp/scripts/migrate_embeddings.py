#!/usr/bin/env python3
"""ChromaDB の埋め込みを intfloat/multilingual-e5-base に移行するスクリプト。

使い方:
    cd memory-mcp
    uv run python scripts/migrate_embeddings.py

注意:
    - 既存の all-MiniLM-L6-v2 (384次元) から multilingual-e5-base (768次元) に移行
    - 旧コレクションは削除される（実行前にバックアップ推奨）
    - 実行後は元のモデルとの互換性なし
"""

from __future__ import annotations

import sys
from pathlib import Path

# プロジェクトルートを sys.path に追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chromadb

from memory_mcp.config import MemoryConfig
from memory_mcp.embedding import E5EmbeddingFunction
from memory_mcp.normalizer import normalize_japanese


def migrate(config: MemoryConfig) -> None:
    """ChromaDB の全記憶を e5 モデルで再 embedding する。"""
    print(f"DB パス: {config.db_path}")
    print(f"コレクション名: {config.collection_name}")
    print(f"埋め込みモデル: {config.embedding_model}")
    print()

    client = chromadb.PersistentClient(path=config.db_path)

    try:
        old_collection = client.get_collection(name=config.collection_name)
    except Exception:
        print(f"コレクション '{config.collection_name}' が見つかりません。")
        sys.exit(1)

    result = old_collection.get(include=["documents", "metadatas"])
    ids = result.get("ids", [])
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []

    if not ids:
        print("記憶が0件です。移行不要。")
        return

    print(f"移行対象: {len(ids)} 件")
    print()
    answer = input("続行しますか？ 旧コレクションは削除されます (y/N): ")
    if answer.strip().lower() != "y":
        print("キャンセルしました。")
        sys.exit(0)

    # e5 埋め込み関数を初期化
    print("モデルをロード中...")
    ef = E5EmbeddingFunction(config.embedding_model)
    ef._load_model()
    print(f"モデル '{config.embedding_model}' のロード完了")
    print()

    # 旧コレクション削除（次元数が異なるため互換性なし）
    print("旧コレクションを削除して新コレクションを作成...")
    client.delete_collection(config.collection_name)

    # 新コレクション作成（e5 埋め込み関数で）
    new_collection = client.create_collection(
        name=config.collection_name,
        embedding_function=ef,
        metadata={
            "description": "Codex's long-term memories",
            "embedding_model": config.embedding_model,
        },
    )

    # バッチで正規化 + 再 embedding して追加
    batch_size = 32
    total = len(ids)
    for i in range(0, total, batch_size):
        batch_ids = ids[i : i + batch_size]
        batch_docs = documents[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]

        normalized_docs = [normalize_japanese(doc) if doc else "" for doc in batch_docs]

        new_collection.add(
            ids=batch_ids,
            documents=normalized_docs,
            metadatas=batch_metas,
        )

        done = min(i + batch_size, total)
        print(f"  {done}/{total} 件完了", end="\r", flush=True)

    print(f"\n移行完了: {total} 件を '{config.embedding_model}' (768次元) で再 embedding しました。")


def main() -> None:
    config = MemoryConfig.from_env()
    migrate(config)


if __name__ == "__main__":
    main()
