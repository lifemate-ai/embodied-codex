"""Tests for AssociationEngine batch fetching (Phase 10)."""

from __future__ import annotations

import pytest

from memory_mcp.association import AssociationEngine
from memory_mcp.types import Memory


def _make_memory(memory_id: str, linked_ids: tuple[str, ...] = ()) -> Memory:
    return Memory(
        id=memory_id,
        content=f"memory {memory_id}",
        timestamp="2026-01-01T00:00:00",
        emotion="neutral",
        importance=3,
        category="daily",
        linked_ids=linked_ids,
    )


class TestAssociationEngineSpread:
    """AssociationEngine.spread() のバッチ取得テスト。"""

    @pytest.mark.asyncio
    async def test_empty_seeds_returns_empty(self) -> None:
        """seeds が空なら何もしない。"""
        engine = AssociationEngine()
        call_count = 0

        async def fetch(ids: list[str]) -> list[Memory]:
            nonlocal call_count
            call_count += 1
            return []

        expanded, _ = await engine.spread(
            seeds=[],
            fetch_memories_by_ids=fetch,
            max_branches=3,
            max_depth=2,
        )
        assert expanded == []
        assert call_count == 0

    @pytest.mark.asyncio
    async def test_depth1_single_batch_call(self) -> None:
        """深さ1 のとき fetch は 1回だけ呼ばれる（N+1 → 1）。"""
        engine = AssociationEngine()

        # seed A → B, C にリンク
        seed = _make_memory("A", linked_ids=("B", "C"))
        db = {
            "B": _make_memory("B"),
            "C": _make_memory("C"),
        }
        fetch_calls: list[list[str]] = []

        async def fetch(ids: list[str]) -> list[Memory]:
            fetch_calls.append(ids)
            return [db[i] for i in ids if i in db]

        expanded, diag = await engine.spread(
            seeds=[seed],
            fetch_memories_by_ids=fetch,
            max_branches=5,
            max_depth=1,
        )

        assert len(fetch_calls) == 1  # バッチは1回
        assert set(fetch_calls[0]) == {"B", "C"}
        assert {m.id for m in expanded} == {"B", "C"}
        assert diag.expanded_nodes == 2

    @pytest.mark.asyncio
    async def test_depth2_two_batch_calls(self) -> None:
        """深さ2 のとき fetch は 2回呼ばれる（深さ × 1）。"""
        engine = AssociationEngine()

        seed = _make_memory("A", linked_ids=("B",))
        b = _make_memory("B", linked_ids=("C",))
        c = _make_memory("C")
        db = {"B": b, "C": c}
        fetch_calls: list[list[str]] = []

        async def fetch(ids: list[str]) -> list[Memory]:
            fetch_calls.append(ids)
            return [db[i] for i in ids if i in db]

        expanded, diag = await engine.spread(
            seeds=[seed],
            fetch_memories_by_ids=fetch,
            max_branches=5,
            max_depth=2,
        )

        assert len(fetch_calls) == 2  # 深さ1回目: B, 深さ2回目: C
        assert fetch_calls[0] == ["B"]
        assert fetch_calls[1] == ["C"]
        assert {m.id for m in expanded} == {"B", "C"}

    @pytest.mark.asyncio
    async def test_no_duplicate_fetch(self) -> None:
        """複数の seed が同じ隣接 ID を持つとき、重複取得しない。"""
        engine = AssociationEngine()

        seed1 = _make_memory("A", linked_ids=("C",))
        seed2 = _make_memory("B", linked_ids=("C",))  # 同じ C を参照
        db = {"C": _make_memory("C")}
        fetched_ids: list[str] = []

        async def fetch(ids: list[str]) -> list[Memory]:
            fetched_ids.extend(ids)
            return [db[i] for i in ids if i in db]

        expanded, _ = await engine.spread(
            seeds=[seed1, seed2],
            fetch_memories_by_ids=fetch,
            max_branches=5,
            max_depth=1,
        )

        assert fetched_ids.count("C") == 1  # 重複取得なし
        assert len(expanded) == 1

    @pytest.mark.asyncio
    async def test_seeds_not_re_fetched(self) -> None:
        """seed 自体は fetch されない（visited に含まれる）。"""
        engine = AssociationEngine()

        seed = _make_memory("A", linked_ids=("A",))  # 自己参照
        fetch_called = False

        async def fetch(ids: list[str]) -> list[Memory]:
            nonlocal fetch_called
            if "A" in ids:
                fetch_called = True
            return []

        await engine.spread(
            seeds=[seed],
            fetch_memories_by_ids=fetch,
            max_branches=5,
            max_depth=2,
        )

        assert not fetch_called  # seed A は fetch されない

    @pytest.mark.asyncio
    async def test_max_branches_respected(self) -> None:
        """max_branches で各ノードの隣接数を制限する。"""
        engine = AssociationEngine()

        # A → B, C, D, E, F (5件)
        seed = _make_memory("A", linked_ids=("B", "C", "D", "E", "F"))
        db = {i: _make_memory(i) for i in "BCDEF"}
        fetched_ids: list[str] = []

        async def fetch(ids: list[str]) -> list[Memory]:
            fetched_ids.extend(ids)
            return [db[i] for i in ids if i in db]

        await engine.spread(
            seeds=[seed],
            fetch_memories_by_ids=fetch,
            max_branches=3,  # 3件に制限
            max_depth=1,
        )

        assert len(fetched_ids) == 3  # 5件あっても3件だけ取得
