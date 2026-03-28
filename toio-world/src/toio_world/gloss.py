from __future__ import annotations


def suggest_glosses(symbol: str) -> list[str]:
    if symbol.startswith("ACT_"):
        return _suggest_action_glosses(symbol)
    if symbol.startswith("HEADING_"):
        heading = symbol.removeprefix("HEADING_")
        return [f"heading {heading.lower()}", f"{heading.lower()}-facing"]
    if symbol.startswith("NEAR_EDGE_"):
        axis = symbol.removeprefix("NEAR_EDGE_").lower()
        return [f"near {axis} edge", f"{axis} edge zone"]
    if symbol.startswith("X_") or symbol.startswith("Y_"):
        axis, level = symbol.split("_", 1)
        return [f"{axis.lower()} {level.lower()} zone"]
    if symbol.startswith("MARKER_"):
        marker = symbol.removeprefix("MARKER_")
        return [f"on marker {marker}"]

    direct = {
        "MOVE_FAIL": ["movement fails", "stuck"],
        "MOVE_SMALL": ["small movement"],
        "MOVE_LARGE": ["large movement"],
        "ROT_LEFT": ["rotate left"],
        "ROT_RIGHT": ["rotate right"],
        "ROT_NONE": ["no rotation"],
        "POS_X_PLUS": ["x increases"],
        "POS_X_MINUS": ["x decreases"],
        "POS_Y_PLUS": ["y increases"],
        "POS_Y_MINUS": ["y decreases"],
        "TRANSITION_VALID": ["valid transition"],
        "TRANSITION_UNKNOWN": ["uncertain transition"],
    }
    return direct.get(symbol, [symbol.lower()])


def suggest_concept_glosses(name: str, symbols: list[str]) -> list[str]:
    symbol_set = set(symbols)
    if {"X_HIGH", "NEAR_EDGE_X_MAX"} <= symbol_set:
        return ["x-max edge zone", "far-right zone"]
    if {"X_LOW", "NEAR_EDGE_X_MIN"} <= symbol_set:
        return ["x-min edge zone", "far-left zone"]
    if {"Y_HIGH", "NEAR_EDGE_Y_MAX"} <= symbol_set:
        return ["y-max edge zone"]
    if {"Y_LOW", "NEAR_EDGE_Y_MIN"} <= symbol_set:
        return ["y-min edge zone"]
    if any(symbol.startswith("HEADING_") for symbol in symbols):
        return [f"compound state: {name.lower()}"]
    return [name.lower().replace("__", " ")]


def suggest_macro_glosses(preconditions: list[str], action_symbols: list[str]) -> list[str]:
    action_bits = [_primary_gloss(symbol) for symbol in action_symbols]
    action_phrase = " then ".join(action_bits)
    if preconditions:
        condition_bits = [_primary_gloss(symbol) for symbol in preconditions]
        condition_phrase = " and ".join(condition_bits)
        return [
            f"when {condition_phrase}: {action_phrase}",
            f"{action_phrase} under {condition_phrase}",
        ]
    return [action_phrase]


def suggest_rule_glosses(antecedent: list[str], consequent: str) -> list[str]:
    if not antecedent:
        return [_primary_gloss(consequent)]
    premise = " and ".join(_primary_gloss(symbol) for symbol in antecedent)
    result = _primary_gloss(consequent)
    return [
        f"if {premise}, then {result}",
        f"{premise} predicts {result}",
    ]


def _suggest_action_glosses(symbol: str) -> list[str]:
    action = symbol.removeprefix("ACT_")
    table = {
        "FORWARD_SHORT": ["forward short", "small forward move"],
        "FORWARD_LONG": ["forward long", "large forward move"],
        "BACKWARD_SHORT": ["backward short", "small backward move"],
        "TURN_LEFT_SMALL": ["small left turn"],
        "TURN_RIGHT_SMALL": ["small right turn"],
        "TURN_LEFT_LARGE": ["large left turn"],
        "TURN_RIGHT_LARGE": ["large right turn"],
        "STOP": ["stop"],
    }
    return table.get(action, [action.lower()])


def _primary_gloss(symbol: str) -> str:
    suggestions = suggest_glosses(symbol)
    return suggestions[0] if suggestions else symbol.lower()
