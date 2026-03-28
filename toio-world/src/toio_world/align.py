from __future__ import annotations

from pathlib import Path

from .gloss import suggest_glosses
from .protolang import GlossTable, SymbolizedStep


def build_gloss_table(observations: list[SymbolizedStep]) -> GlossTable:
    symbols: list[str] = []
    for item in observations:
        symbols.extend(item.pre_state_symbols)
        symbols.append(item.action_symbol)
        symbols.extend(item.change_symbols)
        symbols.extend(item.post_state_symbols)
    table = GlossTable.from_symbols(symbols)
    for entry in table.entries:
        entry.suggested_glosses = suggest_glosses(entry.symbol)
    return table


def save_gloss_table(observations: list[SymbolizedStep], path: str | Path) -> None:
    build_gloss_table(observations).save(path)
