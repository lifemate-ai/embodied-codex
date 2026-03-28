from __future__ import annotations

from pathlib import Path

from .align import build_gloss_table
from .concepts import discover_state_concepts
from .discover import discover_action_macros, mine_transition_rules
from .induce import derive_symbolized_steps, symbol_counts
from .logger import load_episode
from .protolang import PrimitiveSymbolConfig, load_gloss_table
from .vocabulary import compile_working_vocabulary


def review_protolang(
    episode_path: str | Path,
    *,
    top_k: int = 10,
    max_state_arity: int = 2,
) -> dict:
    path = Path(episode_path)
    bundle = load_episode(path)
    observations = derive_symbolized_steps(bundle, PrimitiveSymbolConfig())
    counts = symbol_counts(observations)
    macros = discover_action_macros(
        observations,
        min_support=2,
        max_length=2,
        state_conditioned=True,
    )
    concepts = discover_state_concepts(
        observations,
        min_support=2,
        min_confidence=0.8,
        max_size=2,
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
    vocabulary = compile_working_vocabulary(
        observations,
        episode_id=bundle.meta.episode_id,
        gloss_table=gloss_table,
        concepts=concepts,
        macros=macros,
        rules=rules,
        per_kind_limit=top_k,
        sources={
            "episode_path": str(path),
            "gloss_path": str(gloss_path),
        },
    )

    unresolved = [entry.symbol for entry in gloss_table.entries if not entry.gloss][:top_k]
    return {
        "episode_id": bundle.meta.episode_id,
        "top_symbols": list(counts.items())[:top_k],
        "top_concepts": [concept.model_dump(mode="json") for concept in concepts.concepts[:top_k]],
        "top_macros": [macro.model_dump(mode="json") for macro in macros.macros[:top_k]],
        "top_rules": [rule.model_dump(mode="json") for rule in rules.rules[:top_k]],
        "top_vocabulary": [entry.model_dump(mode="json") for entry in vocabulary.entries],
        "unglossed_symbols": unresolved,
        "gloss_path": str(gloss_path),
    }
