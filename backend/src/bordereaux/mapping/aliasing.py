"""Stage 1 (exact) and Stage 2 (fuzzy) resolution against the canonical
schema's alias lists (data dictionary resolution order, §3 of the research
notes / ``resolution`` block in ``bordereaux_pc_v1.yaml``)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

_PUNCT_RE = re.compile(r"[^a-z0-9\s]")
_WS_RE = re.compile(r"\s+")


def normalize_alias(text: str) -> str:
    """lower -> separators to spaces -> strip punctuation -> collapse spaces.

    ``%`` becomes the word "pct" rather than being stripped to nothing -
    otherwise "Commission %" and "Commission" would both normalize to
    "commission" and collide with two genuinely different canonical fields
    (``commission_pct`` vs ``commission``)."""
    t = str(text).strip().lower()
    t = t.replace("%", " pct ")
    t = t.replace("_", " ").replace("-", " ").replace("/", " ")
    t = _PUNCT_RE.sub(" ", t)
    t = _WS_RE.sub(" ", t).strip()
    return t


@dataclass(frozen=True)
class CanonicalFieldDef:
    name: str
    display_name: str
    type: str
    required: str
    category: str
    money_role: str | None
    high_risk: bool
    aliases_normalized: frozenset[str] = field(default_factory=frozenset)


def build_field_index(definition: dict[str, Any]) -> list[CanonicalFieldDef]:
    fields: list[CanonicalFieldDef] = []
    for f in definition["fields"]:
        aliases = {normalize_alias(a) for a in f.get("aliases", [])}
        aliases.add(normalize_alias(f["name"]))
        aliases.add(normalize_alias(f["display_name"]))
        fields.append(
            CanonicalFieldDef(
                name=f["name"],
                display_name=f["display_name"],
                type=f.get("type", "STRING"),
                required=f.get("required", "optional"),
                category=f.get("category", ""),
                money_role=f.get("money_role"),
                high_risk=bool(f.get("high_risk", False)),
                aliases_normalized=frozenset(a for a in aliases if a),
            )
        )
    return fields


def exact_matches(source_header: str, fields: list[CanonicalFieldDef]) -> list[CanonicalFieldDef]:
    """Every field whose alias set contains the header (aliases such as
    "Line" or "Category" legitimately appear under more than one field)."""
    norm = normalize_alias(source_header)
    if not norm:
        return []
    return [f for f in fields if norm in f.aliases_normalized]


def is_primary_name(source_header: str, f: CanonicalFieldDef) -> bool:
    """Header equals the field's own name or display name (not merely an alias)."""
    norm = normalize_alias(source_header)
    return norm in {normalize_alias(f.name), normalize_alias(f.display_name)}


def exact_match(source_header: str, fields: list[CanonicalFieldDef]) -> CanonicalFieldDef | None:
    norm = normalize_alias(source_header)
    if not norm:
        return None
    for f in fields:
        if norm in f.aliases_normalized:
            return f
    return None


def fuzzy_match(
    source_header: str, fields: list[CanonicalFieldDef], threshold: float = 0.90
) -> tuple[CanonicalFieldDef, float] | None:
    """Best fuzzy match (0-1) across every field's alias set. Returns ``None``
    if nothing clears ``threshold`` - never guesses below it.

    Two measures: plain string similarity (typos: "Nett Prem"), then, when that
    falls short, a token-wise abbreviation match ("Grs Prem" -> "Gross Prem",
    "Pol Nmbr" -> "Pol Number")."""
    norm = normalize_alias(source_header)
    if not norm:
        return None
    best_field: CanonicalFieldDef | None = None
    best_score = 0.0
    for f in fields:
        for alias in f.aliases_normalized:
            score = fuzz.ratio(norm, alias) / 100.0
            if score > best_score:
                best_score = score
                best_field = f
    if best_field is not None and best_score >= threshold:
        return best_field, best_score
    return _abbreviation_match(norm, fields, threshold)


_MIN_TOKEN_SCORE = 0.85


def _is_abbreviation(short: str, full: str) -> bool:
    """``nmbr`` for ``number``: same first letter, letters in order, strictly
    shorter, and at least 40% of the full word."""
    if len(short) < 2 or len(short) >= len(full) or short[0] != full[0] or len(short) < 0.4 * len(full):
        return False
    letters = iter(full)
    return all(ch in letters for ch in short)


def _token_score(source: str, alias: str) -> float:
    if source == alias:
        return 1.0
    if _is_abbreviation(source, alias):
        # The more of the word is kept, the more convincing: "brkr" is closer
        # to "broker" than to "brokerage".
        return 0.85 + 0.10 * len(source) / len(alias)
    return fuzz.ratio(source, alias) / 100.0


def _abbreviation_match(
    norm: str, fields: list[CanonicalFieldDef], threshold: float
) -> tuple[CanonicalFieldDef, float] | None:
    source_tokens = norm.split()
    per_field: dict[str, float] = {}
    by_name = {f.name: f for f in fields}
    for f in fields:
        for alias in f.aliases_normalized:
            alias_tokens = alias.split()
            if len(alias_tokens) != len(source_tokens):
                continue
            scores = [_token_score(s, a) for s, a in zip(source_tokens, alias_tokens)]
            if min(scores) < _MIN_TOKEN_SCORE:
                continue
            mean = sum(scores) / len(scores)
            if mean >= threshold and mean > per_field.get(f.name, 0.0):
                per_field[f.name] = mean
    if not per_field:
        return None
    ranked = sorted(per_field.items(), key=lambda kv: kv[1], reverse=True)
    if len(ranked) > 1 and ranked[0][1] - ranked[1][1] < 0.02:
        return None  # several fields fit equally well: leave it to the reviewer
    return by_name[ranked[0][0]], ranked[0][1]
