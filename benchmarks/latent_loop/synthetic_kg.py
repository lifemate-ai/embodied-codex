"""Synthetic knowledge graph utilities for latent-loop benchmarks."""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticKG:
    entities: list[str]
    relation_maps: dict[str, dict[str, str]]


def build_synthetic_kg(entities: int, relations: int, *, seed: int = 7) -> SyntheticKG:
    rng = random.Random(seed)
    entity_names = [f"e{index}" for index in range(entities)]
    relation_maps: dict[str, dict[str, str]] = {}
    for relation_index in range(relations):
        shuffled = entity_names[:]
        rng.shuffle(shuffled)
        relation_maps[f"r{relation_index}"] = dict(zip(entity_names, shuffled, strict=True))
    return SyntheticKG(entities=entity_names, relation_maps=relation_maps)


def relation_sequence_answer(kg: SyntheticKG, start: str, relations: list[str]) -> str:
    current = start
    for relation in relations:
        current = kg.relation_maps[relation][current]
    return current
