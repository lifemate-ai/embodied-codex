"""Episode memory management (Phase 11: SQLite backend)."""

import asyncio
import uuid
from typing import TYPE_CHECKING

from .types import Episode

if TYPE_CHECKING:
    from .store import MemoryStore


class EpisodeManager:
    """エピソード記憶の管理.

    一連の体験を「エピソード」としてまとめて記憶・検索する。
    例: 「朝の空を探した体験」= 複数の記憶をストーリーとして統合
    """

    def __init__(self, memory_store: "MemoryStore"):
        self._memory_store = memory_store
        self._lock = asyncio.Lock()

    async def create_episode(
        self,
        title: str,
        memory_ids: list[str],
        participants: list[str] | None = None,
        auto_summarize: bool = True,
    ) -> Episode:
        """エピソードを作成."""
        if not memory_ids:
            raise ValueError("memory_ids cannot be empty")

        memories = await self._memory_store.get_by_ids(memory_ids)
        if not memories:
            raise ValueError("No memories found for the given IDs")

        memories.sort(key=lambda m: m.timestamp)

        if auto_summarize:
            summary = " → ".join(m.content[:50] for m in memories)
        else:
            summary = ""

        most_important = max(memories, key=lambda m: m.importance)
        emotion = most_important.emotion

        episode = Episode(
            id=str(uuid.uuid4()),
            title=title,
            start_time=memories[0].timestamp,
            end_time=memories[-1].timestamp if len(memories) > 1 else None,
            memory_ids=tuple(m.id for m in memories),
            participants=tuple(participants or []),
            location_context=None,
            summary=summary,
            emotion=emotion,
            importance=max(m.importance for m in memories),
        )

        await self._memory_store.save_episode(episode)

        for memory in memories:
            await self._memory_store.update_episode_id(memory.id, episode.id)

        return episode

    async def search_episodes(self, query: str, n_results: int = 5) -> list[Episode]:
        """エピソードを検索."""
        return await self._memory_store.search_episodes(query=query, n_results=n_results)

    async def get_episode_by_id(self, episode_id: str) -> Episode | None:
        """エピソードIDから取得."""
        return await self._memory_store.get_episode_by_id(episode_id)

    async def get_episode_memories(self, episode_id: str) -> list:
        """エピソードに含まれる記憶を時系列順で取得."""
        episode = await self.get_episode_by_id(episode_id)
        if episode is None:
            raise ValueError(f"Episode not found: {episode_id}")

        memories = await self._memory_store.get_by_ids(list(episode.memory_ids))
        memories.sort(key=lambda m: m.timestamp)
        return memories

    async def list_all_episodes(self) -> list[Episode]:
        """全エピソードを取得（新しい順）."""
        return await self._memory_store.list_all_episodes()

    async def delete_episode(self, episode_id: str) -> None:
        """エピソードを削除（記憶は削除しない）."""
        episode = await self.get_episode_by_id(episode_id)
        if episode:
            for memory_id in episode.memory_ids:
                try:
                    await self._memory_store.update_episode_id(memory_id, "")
                except ValueError:
                    pass

        await self._memory_store.delete_episode(episode_id)
