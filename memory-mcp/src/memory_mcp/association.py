"""Associative graph expansion for divergent recall."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

from .predictive import query_ambiguity_score
from .types import Memory


def adaptive_search_params(
    context: str,
    requested_branches: int,
    requested_depth: int,
    seed_count: int,
) -> tuple[int, int]:
    """Adapt branch/depth based on query ambiguity and seed confidence."""
    ambiguity = query_ambiguity_score(context)
    if seed_count <= 1:
        ambiguity = min(1.0, ambiguity + 0.2)

    branch_scale = 0.8 + ambiguity
    depth_scale = 0.9 + 0.5 * ambiguity

    branches = int(round(requested_branches * branch_scale))
    depth = int(round(requested_depth * depth_scale))

    branches = max(1, min(8, branches))
    depth = max(1, min(5, depth))
    return branches, depth


@dataclass(frozen=True)
class AssociationDiagnostics:
    """Association traversal diagnostics."""

    branches_used: int
    depth_used: int
    traversed_edges: int
    expanded_nodes: int
    avg_branching_factor: float


class AssociationEngine:
    """Graph traversal based on explicit and implicit links."""

    async def spread(
        self,
        seeds: list[Memory],
        fetch_memories_by_ids: Callable[[list[str]], Awaitable[list[Memory]]],
        max_branches: int,
        max_depth: int,
    ) -> tuple[list[Memory], AssociationDiagnostics]:
        """Expand associative neighborhood from seed memories.

        Uses batch fetching per depth level (N+1 → depth×1 DB calls).
        """
        if not seeds:
            return [], AssociationDiagnostics(max_branches, max_depth, 0, 0, 0.0)

        visited: set[str] = {m.id for m in seeds}
        current_level: list[Memory] = list(seeds)
        expanded: list[Memory] = []
        traversed_edges = 0
        branching_counts: list[int] = []

        for _depth in range(max_depth):
            if not current_level:
                break

            # 現在レベルの全メモリから未訪問の隣接IDを収集
            frontier_ids: list[str] = []
            for memory in current_level:
                neighbors = self._neighbor_candidates(memory)[:max_branches]
                branching_counts.append(len(neighbors))
                for neighbor_id in neighbors:
                    traversed_edges += 1
                    if neighbor_id not in visited:
                        frontier_ids.append(neighbor_id)
                        visited.add(neighbor_id)  # 重複取得防止

            if not frontier_ids:
                break

            # 深さ1レベル分をバッチで一括取得（N+1 → 1回）
            fetched = await fetch_memories_by_ids(frontier_ids)
            expanded.extend(fetched)
            current_level = fetched

        avg_branch = 0.0
        if branching_counts:
            avg_branch = sum(branching_counts) / len(branching_counts)

        diagnostics = AssociationDiagnostics(
            branches_used=max_branches,
            depth_used=max_depth,
            traversed_edges=traversed_edges,
            expanded_nodes=len(expanded),
            avg_branching_factor=avg_branch,
        )
        return expanded, diagnostics

    def _neighbor_candidates(self, memory: Memory) -> list[str]:
        """Collect neighbors ordered by confidence."""
        weighted_ids: list[tuple[str, float]] = []
        weighted_ids.extend((item_id, 1.0) for item_id in memory.linked_ids)

        for link in memory.links:
            base = 0.8
            if link.link_type == "similar":
                base = 1.0
            elif link.link_type in {"related", "caused_by", "leads_to"}:
                base = 0.85
            weighted_ids.append((link.target_id, base))

        for target_id, weight in memory.coactivation_weights:
            weighted_ids.append((target_id, max(0.0, min(1.0, weight))))

        dedup: dict[str, float] = {}
        for target_id, weight in weighted_ids:
            if target_id not in dedup or dedup[target_id] < weight:
                dedup[target_id] = weight

        ordered = sorted(dedup.items(), key=lambda item: item[1], reverse=True)
        return [target_id for target_id, _ in ordered]

