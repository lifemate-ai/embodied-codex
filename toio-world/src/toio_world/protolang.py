from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class PrimitiveSymbolConfig(BaseModel):
    edge_margin_ratio: float = 0.15
    movement_fail_threshold: float = 5.0
    movement_large_threshold: float = 30.0
    rotation_threshold_deg: float = 10.0


class SymbolizedStep(BaseModel):
    episode_id: str
    step: int
    ts: str
    pre_state_symbols: list[str] = Field(default_factory=list)
    action_symbol: str
    change_symbols: list[str] = Field(default_factory=list)
    post_state_symbols: list[str] = Field(default_factory=list)


class GlossEntry(BaseModel):
    symbol: str
    gloss: str | None = None
    suggested_glosses: list[str] = Field(default_factory=list)
    note: str = ""
    examples: list[str] = Field(default_factory=list)


class GlossTable(BaseModel):
    entries: list[GlossEntry] = Field(default_factory=list)

    @classmethod
    def from_symbols(cls, symbols: list[str]) -> "GlossTable":
        return cls(entries=[GlossEntry(symbol=symbol) for symbol in sorted(set(symbols))])

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


def load_gloss_table(path: str | Path) -> GlossTable:
    return GlossTable.model_validate_json(Path(path).read_text(encoding="utf-8"))


class MacroCandidate(BaseModel):
    name: str
    action_symbols: list[str]
    preconditions: list[str] = Field(default_factory=list)
    support: int
    confidence: float = 0.0
    score: float = 0.0
    examples: list[str] = Field(default_factory=list)


class ConceptCandidate(BaseModel):
    name: str
    symbols: list[str]
    support: int
    confidence: float
    score: float = 0.0
    suggested_glosses: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class RuleCandidate(BaseModel):
    antecedent: list[str]
    consequent: str
    support: int
    confidence: float
    score: float = 0.0
    examples: list[str] = Field(default_factory=list)


class MacroCatalog(BaseModel):
    macros: list[MacroCandidate] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


class RuleCatalog(BaseModel):
    rules: list[RuleCandidate] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )


class ConceptCatalog(BaseModel):
    concepts: list[ConceptCandidate] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=True, indent=2),
            encoding="utf-8",
        )
