"""Confidence scoring (ADR-004, revised).

Python does the math, the breakdown is retained as evidence, and the AI
bucket stays at its neutral 0.5 default in no-LLM mode.

Revision: the ``relationship`` bucket (no column relationships are defined at
mapping time - the arithmetic check now runs in financial checks, after
treaty figures are entered) and the ``historical`` bucket (no learning from
past manual mappings) were removed and their weight redistributed.

A column whose name is a data-dictionary term for the target field it maps to
is a deterministic, fully-explained match and scores 100% outright
(``EXACT_DICTIONARY_CONFIDENCE``), bypassing the weighted sum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

WEIGHTS: dict[str, float] = {
    "semantic": 0.30,
    "value": 0.25,
    "context": 0.20,
    "layout": 0.10,
    "ai": 0.15,
}

EXACT_DICTIONARY_CONFIDENCE = 1.0


def calculate_confidence(scores: dict[str, float]) -> float:
    total = sum(scores.get(k, 0.5 if k == "ai" else 0.0) * w for k, w in WEIGHTS.items())  # ai: neutral default when no LLM
    return min(max(total, 0.0), 1.0)


def exact_dictionary_breakdown() -> dict[str, float]:
    return {k: 1.0 for k in WEIGHTS}


@dataclass
class ScoredCandidate:
    source_column: str
    target_field: str
    stage: str  # ResolutionStage value
    breakdown: dict[str, float]
    total: float
    evidence: list[dict[str, Any]] = field(default_factory=list)
    is_ambiguous: bool = False

    @property
    def auto_approve_eligible(self) -> bool:
        """Never auto-approve anything the mapping resolved by anything less
        certain than an exact alias match (ADR-002/§4: "never silently
        accept an ambiguous financial mapping merely because its column name
        looks similar"). Fuzzy/semantic/human-review candidates always need
        an explicit human approval, however high their numeric score."""
        return self.stage == "EXACT" and not self.is_ambiguous and self.total >= 0.80


def confidence_total_decimal(total: float) -> Decimal:
    # ExactDecimal(5,4) columns top out at 9.9999 - clamp defensively.
    return Decimal(str(round(min(max(total, 0.0), 1.0), 4)))


def value_type_score(column_type: str, field_type: str) -> float:
    """How plausible a column of profiled type ``column_type`` is for a field of ``field_type``."""
    numeric_types = {"INTEGER", "DECIMAL", "PERCENTAGE"}
    if column_type in numeric_types and field_type in numeric_types:
        return 1.0
    if column_type == field_type:
        return 1.0
    if column_type == "STRING" and field_type in ("STRING", "ENUM", "COUNTRY_CODE", "CURRENCY_CODE"):
        return 0.8
    if column_type == "UNKNOWN":
        return 0.5
    return 0.3
