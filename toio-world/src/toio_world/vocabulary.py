from __future__ import annotations

import json
from collections import Counter, defaultdict
from math import log1p
from pathlib import Path

from pydantic import BaseModel, Field

from .align import build_gloss_table
from .concepts import discover_state_concepts
from .discover import discover_action_macros, mine_transition_rules
from .gloss import (
    suggest_concept_glosses,
    suggest_glosses,
    suggest_macro_glosses,
    suggest_rule_glosses,
)
from .induce import derive_symbolized_steps, symbol_counts
from .logger import load_episode
from .protolang import (
    ConceptCatalog,
    GlossTable,
    MacroCatalog,
    PrimitiveSymbolConfig,
    RuleCatalog,
    SymbolizedStep,
    load_gloss_table,
)


class VocabularyEntry(BaseModel):
    kind: str
    name: str
    score: float
    support: int
    confidence: float | None = None
    components: list[str] = Field(default_factory=list)
    selected_gloss: str | None = None
    suggested_glosses: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    note: str = ""


class WorkingVocabulary(BaseModel):
    episode_id: str
    entries: list[VocabularyEntry] = Field(default_factory=list)
    stats: dict[str, int] = Field(default_factory=dict)
    sources: dict[str, str] = Field(default_factory=dict)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def compile_working_vocabulary(
    observations: list[SymbolizedStep],
    *,
    episode_id: str,
    gloss_table: GlossTable,
    concepts: ConceptCatalog,
    macros: MacroCatalog,
    rules: RuleCatalog,
    per_kind_limit: int | None = None,
    sources: dict[str, str] | None = None,
) -> WorkingVocabulary:
    entries: list[VocabularyEntry] = []
    entries.extend(_symbol_entries(observations, gloss_table))
    entries.extend(_concept_entries(concepts, gloss_table))
    entries.extend(_macro_entries(macros))
    entries.extend(_rule_entries(rules))
    entries = _sort_entries(entries)
    if per_kind_limit is not None:
        entries = _limit_per_kind(entries, per_kind_limit)
    stats = Counter(entry.kind for entry in entries)
    return WorkingVocabulary(
        episode_id=episode_id,
        entries=entries,
        stats=dict(stats),
        sources=sources or {},
    )


def compile_episode_vocabulary(
    episode_path: str | Path,
    *,
    top_k_per_kind: int | None = None,
    max_state_arity: int = 2,
) -> WorkingVocabulary:
    path = Path(episode_path)
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    concepts = discover_state_concepts(
        observations,
        min_support=2,
        min_confidence=0.8,
        max_size=2,
    )
    macros = discover_action_macros(
        observations,
        min_support=2,
        max_length=2,
        state_conditioned=True,
    )
    rules = mine_transition_rules(
        observations,
        min_support=2,
        min_confidence=0.8,
        drop_low_value=True,
        max_state_arity=max_state_arity,
    )
    gloss_path = path / "gloss-table.json"
    if gloss_path.exists():
        gloss_table = load_gloss_table(gloss_path)
    else:
        gloss_table = build_gloss_table(observations)
    return compile_working_vocabulary(
        observations,
        episode_id=bundle.meta.episode_id,
        gloss_table=gloss_table,
        concepts=concepts,
        macros=macros,
        rules=rules,
        per_kind_limit=top_k_per_kind,
        sources={
            "episode_path": str(path),
            "gloss_path": str(gloss_path),
        },
    )


def _symbol_entries(
    observations: list[SymbolizedStep],
    gloss_table: GlossTable,
) -> list[VocabularyEntry]:
    counts = symbol_counts(observations)
    examples = _symbol_examples(observations)
    gloss_lookup = {entry.symbol: entry for entry in gloss_table.entries}
    entries: list[VocabularyEntry] = []
    for symbol, support in counts.items():
        gloss_entry = gloss_lookup.get(symbol)
        suggested_glosses = (
            gloss_entry.suggested_glosses
            if gloss_entry and gloss_entry.suggested_glosses
            else suggest_glosses(symbol)
        )
        entries.append(
            VocabularyEntry(
                kind="symbol",
                name=symbol,
                score=round(log1p(support) * _symbol_weight(symbol), 3),
                support=support,
                components=[symbol],
                selected_gloss=gloss_entry.gloss if gloss_entry else None,
                suggested_glosses=suggested_glosses,
                examples=examples[symbol][:5],
                note=gloss_entry.note if gloss_entry else "",
            )
        )
    return entries


def _concept_entries(concepts: ConceptCatalog, gloss_table: GlossTable) -> list[VocabularyEntry]:
    gloss_lookup = {entry.symbol: entry for entry in gloss_table.entries}
    entries: list[VocabularyEntry] = []
    for concept in concepts.concepts:
        gloss_entry = gloss_lookup.get(concept.name)
        suggested_glosses = (
            gloss_entry.suggested_glosses
            if gloss_entry and gloss_entry.suggested_glosses
            else suggest_concept_glosses(concept.name, concept.symbols)
        )
        entries.append(
            VocabularyEntry(
                kind="concept",
                name=concept.name,
                score=concept.score,
                support=concept.support,
                confidence=concept.confidence,
                components=concept.symbols,
                selected_gloss=gloss_entry.gloss if gloss_entry else None,
                suggested_glosses=suggested_glosses,
                examples=concept.examples,
                note=gloss_entry.note if gloss_entry else "",
            )
        )
    return entries


def _macro_entries(macros: MacroCatalog) -> list[VocabularyEntry]:
    return [
        VocabularyEntry(
            kind="macro",
            name=macro.name,
            score=macro.score,
            support=macro.support,
            confidence=macro.confidence,
            components=[*macro.preconditions, *macro.action_symbols],
            suggested_glosses=suggest_macro_glosses(macro.preconditions, macro.action_symbols),
            examples=macro.examples,
        )
        for macro in macros.macros
    ]


def _rule_entries(rules: RuleCatalog) -> list[VocabularyEntry]:
    return [
        VocabularyEntry(
            kind="rule",
            name=_rule_name(rule.antecedent, rule.consequent),
            score=rule.score,
            support=rule.support,
            confidence=rule.confidence,
            components=[*rule.antecedent, rule.consequent],
            suggested_glosses=suggest_rule_glosses(rule.antecedent, rule.consequent),
            examples=rule.examples,
        )
        for rule in rules.rules
    ]


def _symbol_examples(observations: list[SymbolizedStep]) -> dict[str, list[str]]:
    examples: dict[str, list[str]] = defaultdict(list)
    for item in observations:
        label = f"{item.episode_id}:{item.step}"
        for symbol in [
            *item.pre_state_symbols,
            item.action_symbol,
            *item.change_symbols,
            *item.post_state_symbols,
        ]:
            if len(examples[symbol]) < 5:
                examples[symbol].append(label)
    return examples


def _symbol_weight(symbol: str) -> float:
    if symbol.startswith("ACT_"):
        return 1.35
    if symbol in {"MOVE_FAIL", "MOVE_LARGE", "ROT_LEFT", "ROT_RIGHT"}:
        return 1.5
    if symbol.startswith("NEAR_EDGE_"):
        return 1.25
    if symbol.startswith("MARKER_"):
        return 1.2
    if symbol in {"TRANSITION_VALID", "ROT_NONE"}:
        return 0.6
    return 1.0


def _sort_entries(entries: list[VocabularyEntry]) -> list[VocabularyEntry]:
    kind_order = {"concept": 0, "macro": 1, "rule": 2, "symbol": 3}
    return sorted(
        entries,
        key=lambda item: (
            kind_order.get(item.kind, 99),
            -item.score,
            -item.support,
            item.name,
        ),
    )


def _limit_per_kind(entries: list[VocabularyEntry], per_kind_limit: int) -> list[VocabularyEntry]:
    counts: Counter[str] = Counter()
    limited: list[VocabularyEntry] = []
    for entry in entries:
        if counts[entry.kind] >= per_kind_limit:
            continue
        limited.append(entry)
        counts[entry.kind] += 1
    return limited


def _rule_name(antecedent: list[str], consequent: str) -> str:
    return "RULE__" + "__".join([*antecedent, consequent])
