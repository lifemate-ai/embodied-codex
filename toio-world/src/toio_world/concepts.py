from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from math import log1p

from .gloss import suggest_concept_glosses
from .protolang import ConceptCandidate, ConceptCatalog, SymbolizedStep


def discover_state_concepts(
    observations: list[SymbolizedStep],
    *,
    min_support: int = 2,
    min_confidence: float = 0.8,
    max_size: int = 2,
) -> ConceptCatalog:
    symbol_counts: Counter[str] = Counter()
    combo_counts: Counter[tuple[str, ...]] = Counter()
    examples: dict[tuple[str, ...], list[str]] = defaultdict(list)

    for item in observations:
        unique_symbols = sorted(set(item.pre_state_symbols))
        symbol_counts.update(unique_symbols)
        for size in range(2, min(max_size, len(unique_symbols)) + 1):
            for combo in combinations(unique_symbols, size):
                combo_counts[combo] += 1
                if len(examples[combo]) < 5:
                    examples[combo].append(f"{item.episode_id}:{item.step}")

    concepts: list[ConceptCandidate] = []
    for combo, support in combo_counts.most_common():
        if support < min_support:
            continue
        base = min(symbol_counts[symbol] for symbol in combo)
        confidence = support / max(base, support)
        if confidence < min_confidence:
            continue
        name = "CONCEPT__" + "__".join(combo)
        score = round(log1p(support) * confidence * (1.0 + 0.1 * len(combo)), 3)
        concepts.append(
            ConceptCandidate(
                name=name,
                symbols=list(combo),
                support=support,
                confidence=round(confidence, 3),
                score=score,
                suggested_glosses=suggest_concept_glosses(name, list(combo)),
                examples=examples[combo],
            )
        )

    concepts.sort(key=lambda item: (-item.score, -item.support, item.name))
    return ConceptCatalog(concepts=concepts)
