from toio_world.concepts import discover_state_concepts
from toio_world.discover import discover_action_macros, mine_transition_rules
from toio_world.protolang import SymbolizedStep


def test_discover_action_macros_finds_repeated_bigrams() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["HEADING_E"],
            action_symbol=action,
            change_symbols=["MOVE_SMALL"],
            post_state_symbols=["HEADING_E"],
        )
        for index, action in enumerate(
            [
                "ACT_FORWARD_LONG",
                "ACT_TURN_LEFT_LARGE",
                "ACT_FORWARD_LONG",
                "ACT_TURN_LEFT_LARGE",
            ]
        )
    ]
    catalog = discover_action_macros(
        observations,
        min_support=2,
        max_length=2,
        state_conditioned=False,
    )
    names = {macro.name for macro in catalog.macros}
    assert "MACRO__ACT_FORWARD_LONG__ACT_TURN_LEFT_LARGE" in names


def test_mine_transition_rules_finds_high_confidence_rule() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["HEADING_E"],
            action_symbol="ACT_FORWARD_SHORT",
            change_symbols=["POS_X_PLUS", "MOVE_SMALL"],
            post_state_symbols=["HEADING_E"],
        )
        for index in range(3)
    ]
    catalog = mine_transition_rules(observations, min_support=2, min_confidence=0.9)
    consequents = {(tuple(rule.antecedent), rule.consequent) for rule in catalog.rules}
    assert (("HEADING_E", "ACT_FORWARD_SHORT"), "POS_X_PLUS") in consequents


def test_state_conditioned_macros_keep_preconditions() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["HEADING_E", "X_LOW"],
            action_symbol=action,
            change_symbols=["MOVE_SMALL"],
            post_state_symbols=["HEADING_E"],
        )
        for index, action in enumerate(
            [
                "ACT_FORWARD_LONG",
                "ACT_TURN_LEFT_LARGE",
                "ACT_FORWARD_LONG",
                "ACT_TURN_LEFT_LARGE",
            ]
        )
    ]
    catalog = discover_action_macros(
        observations,
        min_support=2,
        max_length=2,
        state_conditioned=True,
    )
    assert any(macro.preconditions for macro in catalog.macros)


def test_mine_transition_rules_drops_low_value_defaults() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["HEADING_E"],
            action_symbol="ACT_FORWARD_SHORT",
            change_symbols=["TRANSITION_VALID", "ROT_NONE", "POS_X_PLUS"],
            post_state_symbols=["HEADING_E"],
        )
        for index in range(3)
    ]
    catalog = mine_transition_rules(observations, min_support=2, min_confidence=0.9)
    consequents = {rule.consequent for rule in catalog.rules}
    assert "POS_X_PLUS" in consequents
    assert "TRANSITION_VALID" not in consequents
    assert "ROT_NONE" not in consequents


def test_mine_transition_rules_can_use_two_state_symbols() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["HEADING_E", "NEAR_EDGE_X_MAX"],
            action_symbol="ACT_FORWARD_SHORT",
            change_symbols=["MOVE_FAIL"],
            post_state_symbols=["HEADING_E"],
        )
        for index in range(3)
    ]
    catalog = mine_transition_rules(
        observations,
        min_support=2,
        min_confidence=0.9,
        max_state_arity=2,
    )
    antecedents = {tuple(rule.antecedent) for rule in catalog.rules}
    assert ("HEADING_E", "NEAR_EDGE_X_MAX", "ACT_FORWARD_SHORT") in antecedents


def test_discover_state_concepts_finds_cooccurring_bundle() -> None:
    observations = [
        SymbolizedStep(
            episode_id="e1",
            step=index,
            ts=f"2026-03-29T00:00:0{index}+00:00",
            pre_state_symbols=["X_HIGH", "NEAR_EDGE_X_MAX", "HEADING_E"],
            action_symbol="ACT_FORWARD_SHORT",
            change_symbols=["MOVE_FAIL"],
            post_state_symbols=["X_HIGH", "NEAR_EDGE_X_MAX"],
        )
        for index in range(3)
    ]
    catalog = discover_state_concepts(observations, min_support=2, min_confidence=0.8, max_size=2)
    names = {concept.name for concept in catalog.concepts}
    assert "CONCEPT__NEAR_EDGE_X_MAX__X_HIGH" in names
