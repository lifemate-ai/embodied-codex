from __future__ import annotations

from collections import Counter, defaultdict
from itertools import combinations
from math import log1p

from .protolang import MacroCandidate, MacroCatalog, RuleCandidate, RuleCatalog, SymbolizedStep


def _interestingness(symbol: str) -> float:
    if symbol in {"MOVE_FAIL", "MOVE_LARGE", "ROT_LEFT", "ROT_RIGHT"}:
        return 1.5
    if symbol in {"MOVE_SMALL", "POS_X_PLUS", "POS_X_MINUS", "POS_Y_PLUS", "POS_Y_MINUS"}:
        return 1.2
    if symbol in {"ROT_NONE", "TRANSITION_VALID", "TRANSITION_UNKNOWN"}:
        return 0.4
    return 1.0


def discover_action_macros(
    observations: list[SymbolizedStep],
    *,
    min_support: int = 2,
    max_length: int = 2,
    state_conditioned: bool = False,
) -> MacroCatalog:
    counts: Counter[tuple[str, ...]] = Counter()
    examples: dict[tuple[str, ...], list[str]] = defaultdict(list)
    prefix_counts: Counter[tuple[str, ...]] = Counter()
    action_symbols = [item.action_symbol for item in observations]

    for length in range(2, max_length + 1):
        for start in range(0, max(0, len(action_symbols) - length + 1)):
            base_ngram = tuple(action_symbols[start : start + length])
            keys = [base_ngram]
            if state_conditioned:
                for symbol in observations[start].pre_state_symbols:
                    keys.append((symbol, *base_ngram))
            for ngram in keys:
                counts[ngram] += 1
                prefix_counts[ngram[:-1]] += 1
                if len(examples[ngram]) < 5:
                    examples[ngram].append(
                        f"{observations[start].episode_id}:{observations[start].step}"
                    )

    macros: list[MacroCandidate] = []
    for ngram, support in counts.most_common():
        if support < min_support:
            continue
        conditioned_prefixes = ("HEADING_", "X_", "Y_", "NEAR_EDGE_", "MARKER_")
        if state_conditioned and len(ngram) >= 3 and ngram[0].startswith(conditioned_prefixes):
            preconditions = [ngram[0]]
            action_symbols = list(ngram[1:])
        else:
            preconditions = []
            action_symbols = list(ngram)
        confidence = support / max(prefix_counts[ngram[:-1]], support) if len(ngram) > 1 else 1.0
        score = round(log1p(support) * confidence * (1.0 + 0.2 * len(action_symbols)), 3)
        if preconditions:
            name = "MACRO__" + "__".join(preconditions + action_symbols)
        else:
            name = "MACRO__" + "__".join(action_symbols)
        macros.append(
            MacroCandidate(
                name=name,
                action_symbols=action_symbols,
                preconditions=preconditions,
                support=support,
                confidence=round(confidence, 3),
                score=score,
                examples=examples[ngram],
            )
        )
    macros.sort(key=lambda item: (-item.score, -item.support, item.name))
    return MacroCatalog(macros=macros)


def mine_transition_rules(
    observations: list[SymbolizedStep],
    *,
    min_support: int = 2,
    min_confidence: float = 0.8,
    drop_low_value: bool = True,
    max_state_arity: int = 2,
) -> RuleCatalog:
    antecedent_counts: Counter[tuple[str, ...]] = Counter()
    consequent_counts: dict[tuple[str, ...], Counter[str]] = defaultdict(Counter)
    examples: dict[tuple[tuple[str, ...], str], list[str]] = defaultdict(list)

    for item in observations:
        unique_symbols = sorted(set(item.pre_state_symbols))
        antecedents: list[tuple[str, ...]] = []
        max_arity = max(1, max_state_arity)
        for state_arity in range(1, min(max_arity, len(unique_symbols)) + 1):
            for state_symbols in combinations(unique_symbols, state_arity):
                antecedents.append((*state_symbols, item.action_symbol))
        for antecedent in antecedents:
            antecedent_counts[antecedent] += 1
            for consequent in item.change_symbols:
                consequent_counts[antecedent][consequent] += 1
                key = (antecedent, consequent)
                if len(examples[key]) < 5:
                    examples[key].append(f"{item.episode_id}:{item.step}")

    rules: list[RuleCandidate] = []
    for antecedent, total in antecedent_counts.items():
        for consequent, support in consequent_counts[antecedent].most_common():
            confidence = support / total
            if support < min_support or confidence < min_confidence:
                continue
            if drop_low_value and consequent in {
                "TRANSITION_VALID",
                "TRANSITION_UNKNOWN",
                "ROT_NONE",
            }:
                continue
            specificity = 1.0 + 0.15 * max(0, len(antecedent) - 2)
            score = round(
                log1p(support) * confidence * _interestingness(consequent) * specificity,
                3,
            )
            rules.append(
                RuleCandidate(
                    antecedent=list(antecedent),
                    consequent=consequent,
                    support=support,
                    confidence=round(confidence, 3),
                    score=score,
                    examples=examples[(antecedent, consequent)],
                )
            )
    rules = _dedupe_rules(rules)
    rules.sort(key=lambda item: (-item.score, -item.support, -item.confidence, item.consequent))
    return RuleCatalog(rules=rules)


def _dedupe_rules(rules: list[RuleCandidate]) -> list[RuleCandidate]:
    best_by_signature: dict[tuple[str, str], RuleCandidate] = {}
    for rule in rules:
        action_symbol = rule.antecedent[-1]
        key = (action_symbol, rule.consequent)
        current = best_by_signature.get(key)
        if current is None or (
            rule.score,
            len(rule.antecedent),
            rule.support,
            rule.confidence,
        ) > (
            current.score,
            len(current.antecedent),
            current.support,
            current.confidence,
        ):
            best_by_signature[key] = rule
    return list(best_by_signature.values())
