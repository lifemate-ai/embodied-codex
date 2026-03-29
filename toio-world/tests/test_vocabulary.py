from toio_world.concepts import discover_state_concepts
from toio_world.discover import discover_action_macros, mine_transition_rules
from toio_world.gloss import suggest_rule_glosses
from toio_world.protolang import GlossEntry, GlossTable, SymbolizedStep
from toio_world.vocabulary import compile_working_vocabulary


def _observations() -> list[SymbolizedStep]:
    return [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["X_HIGH", "NEAR_EDGE_X_MAX", "HEADING_E"],
            action_symbol="ACT_FORWARD_LONG" if index % 2 == 0 else "ACT_TURN_LEFT_LARGE",
            change_symbols=["MOVE_FAIL"] if index % 2 else ["MOVE_LARGE"],
            post_state_symbols=["X_HIGH", "NEAR_EDGE_X_MAX"],
        )
        for index in range(4)
    ]


def test_compile_working_vocabulary_keeps_selected_glosses() -> None:
    observations = _observations()
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
        max_state_arity=2,
    )
    gloss_table = GlossTable(
        entries=[
            GlossEntry(
                symbol="MOVE_FAIL",
                gloss="stuck for real",
                suggested_glosses=["movement fails"],
            )
        ]
    )
    vocabulary = compile_working_vocabulary(
        observations,
        episode_id="e1",
        gloss_table=gloss_table,
        concepts=concepts,
        macros=macros,
        rules=rules,
        per_kind_limit=5,
    )
    move_fail = next(entry for entry in vocabulary.entries if entry.name == "MOVE_FAIL")
    assert move_fail.kind == "symbol"
    assert move_fail.selected_gloss == "stuck for real"


def test_compile_working_vocabulary_includes_higher_level_entries() -> None:
    observations = _observations()
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
        max_state_arity=2,
    )
    vocabulary = compile_working_vocabulary(
        observations,
        episode_id="e1",
        gloss_table=GlossTable(entries=[]),
        concepts=concepts,
        macros=macros,
        rules=rules,
    )
    kinds = {entry.kind for entry in vocabulary.entries}
    assert {"symbol", "concept", "macro", "rule"} <= kinds


def test_rule_glosses_produce_human_readable_hints() -> None:
    suggestions = suggest_rule_glosses(
        ["NEAR_EDGE_X_MAX", "ACT_FORWARD_LONG"],
        "MOVE_FAIL",
    )
    assert suggestions
    assert suggestions[0].startswith("if ")
