"""AI assistance for column mapping (ADR-002: deterministic first, AI second).

The deterministic resolver (exact dictionary term -> fuzzy) runs first and settles
what it can. Only the columns it could *not* settle go to the model, in **one**
batched call:

* columns whose header is a dictionary term of several fields (ambiguous alias /
  duplicate-target conflict), and
* columns that matched no field at all (numeric ``extra_*`` pass-throughs, odd
  headers such as "Amount 3", abbreviations in another language, ...).

The model sees everything a person would look at: the target fields (type, aliases,
money role), the profile and sample values of the column, its neighbouring headers
and what the deterministic stage already proposed. Its answer is *validated by
Python* (real field? type-compatible? not already taken? not used twice?) and then
only ever becomes a PROPOSED candidate that a reviewer must approve - it is never
applied automatically and a failed call changes nothing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.models import MappingCandidateStatus, MappingOrigin
from bordereaux.core.utils import to_jsonable
from bordereaux.mapping.scoring import calculate_confidence, confidence_total_decimal, value_type_score
from bordereaux.models.mapping import ApprovedMapping, MappingCandidate

MAX_COLUMNS_PER_CALL = 60
MAX_SAMPLES = 8
MAX_ALIASES = 6
_MIN_TYPE_FIT = 0.5  # below this the column's profiled type clearly cannot be the target's type

SYSTEM_PROMPT = (
    "You are a reinsurance bordereaux data analyst helping map source-file columns to the fields "
    "of a target data dictionary. You only interpret the evidence supplied; you never invent a field "
    "name and you never guess when the evidence is weak (answer null instead). "
    "Reply with a single JSON object and nothing else."
)


@dataclass
class ColumnToResolve:
    column: str
    reason: str  # ambiguous_alias | duplicate_target_conflict | no_dictionary_match | numeric_no_dictionary_match
    proposed: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AiDecision:
    source_column: str
    target_field: str | None
    confidence: float
    reason: str


def _distinct_samples(values: list[Any], limit: int = MAX_SAMPLES) -> list[str]:
    seen: list[str] = []
    for v in values:
        if v is None:
            continue
        text = str(v).strip()
        if text and text not in seen:
            seen.append(text[:60])
        if len(seen) >= limit:
            break
    return seen


def _profile_summary(profile: Any, values: list[Any]) -> dict[str, Any]:
    non_blank = [v for v in values if v not in (None, "")]
    out: dict[str, Any] = {
        "data_type": getattr(profile, "data_type", "UNKNOWN"),
        "filled_rows": len(non_blank),
        "total_rows": len(values),
        "distinct_values": getattr(profile, "distinct_count", None),
    }
    stats = getattr(profile, "numeric_stats", None)
    if isinstance(stats, dict) and stats:
        out["numeric_range"] = {k: stats.get(k) for k in ("min", "max", "mean") if k in stats}
    return out


def build_field_catalog(
    target_fields: list[dict[str, Any]], aliases_of: dict[str, list[str]], taken: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Target fields the model may choose from, and the names already settled elsewhere."""
    catalog: list[dict[str, Any]] = []
    for f in target_fields:
        name = f["name"]
        if name in taken:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "display_name": f.get("display_name", name),
            "type": f.get("type", "STRING"),
        }
        if f.get("money_role"):
            entry["money_role"] = f["money_role"]
        if f.get("required") == "mandatory":
            entry["required"] = True
        aliases = aliases_of.get(name) or []
        if aliases:
            entry["also_known_as"] = aliases[:MAX_ALIASES]
        catalog.append(entry)
    return catalog, sorted(taken)


def build_prompt(
    to_resolve: list[ColumnToResolve],
    *,
    columns: list[str],
    rows: list[dict[str, Any]],
    column_profiles: dict[str, Any],
    catalog: list[dict[str, Any]],
    taken: list[str],
    target_format_mode: str,
) -> str:
    import json

    items: list[dict[str, Any]] = []
    for c in to_resolve:
        idx = columns.index(c.column)
        values = [r.get("values", {}).get(c.column) for r in rows]
        items.append(
            {
                "source_column": c.column,
                "position": idx + 1,
                "previous_column": columns[idx - 1] if idx > 0 else None,
                "next_column": columns[idx + 1] if idx + 1 < len(columns) else None,
                "profile": _profile_summary(column_profiles.get(c.column), values),
                "sample_values": _distinct_samples(values),
                "why_unresolved": c.reason,
                "deterministic_candidates": c.proposed,
            }
        )
    document = {
        "task": (
            "For each entry in columns_to_resolve choose the single best target field from target_fields, "
            "or null when no target field fits (the column is then kept as an extra pass-through column)."
        ),
        "target_format": target_format_mode,
        "rules": [
            "Choose target_field ONLY from target_fields[].name. Never invent names.",
            "Never choose a name listed in already_mapped_fields - those columns are settled.",
            "Use each target field for at most one column; if two columns compete, give it to the better fit and null the other.",
            "A percentage/ratio/rate column is not a money amount; a money amount is not a percentage.",
            "Use the header meaning, the sample values, the data type and the neighbouring columns together.",
            "If the evidence is weak or contradictory answer null with a low confidence rather than guess.",
            "confidence is 0.0-1.0 and must reflect the evidence. reason is at most 25 words and cites the evidence used.",
        ],
        "all_source_columns": columns,
        "columns_to_resolve": items,
        "target_fields": catalog,
        "already_mapped_fields": taken,
        "response_format": {
            "decisions": [
                {"source_column": "<exact source column>", "target_field": "<name or null>", "confidence": 0.0, "reason": "<short>"}
            ]
        },
    }
    return json.dumps(document, ensure_ascii=False, default=str)


def parse_decisions(
    data: Any,
    *,
    sent: dict[str, ColumnToResolve],
    field_types: dict[str, str],
    column_types: dict[str, str],
    taken: set[str],
) -> tuple[dict[str, AiDecision], list[str]]:
    """Validate the model's reply. Returns ``(accepted, rejected_notes)``.

    Only decisions that name a real, free, type-compatible target field survive; one
    decision per column and one column per field (the most confident wins)."""
    notes: list[str] = []
    raw = data.get("decisions") if isinstance(data, dict) else data
    if not isinstance(raw, list):
        return {}, ["The AI reply had no 'decisions' list."]
    best_for_field: dict[str, AiDecision] = {}
    accepted: dict[str, AiDecision] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        column = item.get("source_column")
        if column not in sent:
            notes.append(f"Ignored a decision for unknown column {column!r}.")
            continue
        target = item.get("target_field")
        try:
            confidence = min(1.0, max(0.0, float(item.get("confidence"))))
        except (TypeError, ValueError):
            confidence = 0.5
        reason = str(item.get("reason") or "").strip()[:300]
        if target in (None, "", "null"):
            accepted[column] = AiDecision(column, None, confidence, reason or "AI found no matching target field.")
            continue
        if not isinstance(target, str) or target not in field_types:
            notes.append(f"{column}: AI proposed {target!r}, which is not a target field.")
            continue
        if target in taken:
            notes.append(f"{column}: AI proposed {target}, which is already mapped from another column.")
            continue
        if value_type_score(column_types.get(column, "UNKNOWN"), field_types[target]) < _MIN_TYPE_FIT:
            notes.append(f"{column}: AI proposed {target} but the column's values do not fit that field type.")
            continue
        decision = AiDecision(column, target, confidence, reason)
        rival = best_for_field.get(target)
        if rival is not None and rival.confidence >= confidence:
            notes.append(f"{column}: {target} was given to the more confident column {rival.source_column}.")
            continue
        if rival is not None:
            accepted.pop(rival.source_column, None)
            notes.append(f"{rival.source_column}: {target} was given to the more confident column {column}.")
        best_for_field[target] = decision
        accepted[column] = decision
    return accepted, notes


async def apply_decisions(
    db: AsyncSession,
    mapping_set_id: UUID,
    decisions: dict[str, AiDecision],
    *,
    column_types: dict[str, str],
    field_types: dict[str, str],
    model: str | None,
    provider: str | None,
    actor_id: UUID | None,
) -> int:
    """Turn validated decisions into PROPOSED candidates. Returns how many columns got a suggestion."""
    candidates = list(
        (await db.execute(select(MappingCandidate).where(MappingCandidate.mapping_set_id == mapping_set_id)))
        .scalars()
        .all()
    )
    approved = list(
        (await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == mapping_set_id)))
        .scalars()
        .all()
    )
    by_column: dict[str, list[MappingCandidate]] = {}
    for c in candidates:
        by_column.setdefault(c.source_column, []).append(c)
    approved_by_column = {a.source_column: a for a in approved}
    applied = 0

    for column, d in decisions.items():
        column_candidates = by_column.get(column, [])
        existing = approved_by_column.get(column)
        # A person (or the 100% dictionary match) already decided this column: leave it alone.
        if existing is not None and not (
            existing.origin == MappingOrigin.AUTO_APPROVED.value and existing.target_field.startswith("extra_")
        ):
            continue
        meta = {"model": model, "provider": provider}
        if d.target_field is None:
            # Keep the AI's "no match" opinion visible on the pass-through row.
            for c in column_candidates:
                if c.target_field.startswith("extra_"):
                    c.evidence = to_jsonable(
                        [*c.evidence, {"type": "ai_note", "message": d.reason, "confidence": d.confidence, **meta}]
                    )
            continue
        if any(a.target_field == d.target_field and a.source_column != column for a in approved):
            continue

        vscore = value_type_score(column_types.get(column, "UNKNOWN"), field_types.get(d.target_field, "STRING"))
        suggestion = {
            "type": "ai_suggestion",
            "target_field": d.target_field,
            "confidence": d.confidence,
            "reason": d.reason,
            **meta,
        }
        match = next(
            (
                c
                for c in column_candidates
                if c.target_field == d.target_field and c.status == MappingCandidateStatus.PROPOSED.value
            ),
            None,
        )
        if match is not None:
            breakdown = dict(match.confidence_breakdown or {})
            breakdown["ai"] = d.confidence
            match.confidence_breakdown = to_jsonable(breakdown)
            match.confidence_total = confidence_total_decimal(calculate_confidence(breakdown))
            match.evidence = to_jsonable([*match.evidence, suggestion])
        else:
            breakdown = {"semantic": 0.5, "value": vscore, "context": 0.5, "layout": 0.5, "ai": d.confidence}
            new = MappingCandidate(
                mapping_set_id=mapping_set_id,
                source_column=column,
                target_field=d.target_field,
                confidence_total=confidence_total_decimal(calculate_confidence(breakdown)),
                confidence_breakdown=to_jsonable(breakdown),
                evidence=to_jsonable([suggestion]),
                status=MappingCandidateStatus.PROPOSED.value,
                auto_approve_eligible=False,
            )
            db.add(new)
            column_candidates.append(new)
        # The AI preferred a different field than the deterministic alternatives: say so on them.
        for c in column_candidates:
            if c.target_field == d.target_field or c.status != MappingCandidateStatus.PROPOSED.value:
                continue
            if c.target_field.startswith("extra_"):
                continue
            breakdown = dict(c.confidence_breakdown or {})
            if breakdown:
                breakdown["ai"] = 0.2
                c.confidence_breakdown = to_jsonable(breakdown)
                c.confidence_total = confidence_total_decimal(calculate_confidence(breakdown))
            c.evidence = to_jsonable(
                [
                    *c.evidence,
                    {"type": "ai_preferred_other", "preferred": d.target_field, "reason": d.reason, **meta},
                ]
            )
        applied += 1
    await db.flush()
    return applied


__all__ = [
    "AiDecision",
    "ColumnToResolve",
    "MAX_COLUMNS_PER_CALL",
    "SYSTEM_PROMPT",
    "apply_decisions",
    "build_field_catalog",
    "build_prompt",
    "parse_decisions",
]
