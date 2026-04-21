"""Atomic fact graph helpers for latent-loop-mcp."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .store import LatentLoopStore


def canonical_node(value: str) -> str:
    """Normalize entity node strings."""
    return " ".join(value.strip().lower().split())


def canonical_relation(value: str) -> str:
    """Normalize relation strings."""
    return " ".join(value.strip().lower().replace("_", " ").split())


def merge_fact_metadata(
    existing: dict[str, Any], new: dict[str, Any], *, source: str, source_type: str
) -> dict[str, Any]:
    """Merge fact metadata while preserving provenance."""
    merged = dict(existing)
    merged.update(new)
    sources = list(merged.get("sources", []))
    source_ref = {"source": source, "source_type": source_type}
    if source_ref not in sources:
        sources.append(source_ref)
    merged["sources"] = sources
    return merged


def compose_path(
    store: "LatentLoopStore",
    *,
    start: str,
    relations: list[str],
    max_paths: int = 10,
    min_confidence: float = 0.5,
) -> list[dict[str, Any]]:
    """Deterministically compose a multi-hop path over structured facts."""
    frontier: list[tuple[str, list[str], float, list[str]]] = [(start, [], 1.0, [start])]

    for relation in relations:
        next_frontier: list[tuple[str, list[str], float, list[str]]] = []
        for entity, fact_ids, confidence, entities in frontier:
            edges = store.search_facts(subject=entity, relation=relation, limit=max_paths * 4)
            for edge in edges:
                next_confidence = confidence * edge.confidence
                next_frontier.append(
                    (
                        edge.object,
                        fact_ids + [edge.id],
                        next_confidence,
                        entities + [edge.object],
                    )
                )
        next_frontier.sort(key=lambda item: item[2], reverse=True)
        frontier = next_frontier[:max_paths]
        if not frontier:
            break

    paths = [
        {"entities": entities, "fact_ids": fact_ids, "confidence": confidence}
        for _, fact_ids, confidence, entities in frontier
        if confidence >= min_confidence
    ]
    paths.sort(key=lambda item: item["confidence"], reverse=True)
    return paths[:max_paths]
