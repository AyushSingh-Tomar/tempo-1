"""Deterministic cleaning rules (no AI, no randomness - ADR-002).

Operates on the ``{"columns": [...], "rows": [{"row_number": int, "values": {...}}]}``
shape produced by ``ingestion.service.validate_processing_run`` and produces
the same shape back, plus a before/after summary. Blank rows/columns are
dropped (they carry no data); duplicate rows are flagged, never removed;
nothing with a parseable-but-unusual value is silently rewritten in a way
that changes its meaning - only formatting (whitespace, null tokens, numeric
punctuation) is normalized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bordereaux.cleaning.parsing import (
    detect_number_locale,
    format_partial_date,
    is_ambiguous_number,
    is_null_token,
    looks_partial_date,
    normalize_whitespace,
    try_parse_date,
    try_parse_decimal,
    try_parse_partial_date,
)

_MAX_LOGGED_ITEMS = 200
_TYPE_SNIFF_THRESHOLD = 0.7

# A cell that is *only* a total label ("TOTAL", "Grand Total", "SUBTOTAL (rows 1-15)").
# A name that merely starts with the word ("Total Energies SE") does not match.
_TOTAL_LABEL_RE = re.compile(r"(grand\s+total|sub[\s-]*total|total)s?\s*(?:[(\[:\-].*)?", re.I)
_ROW_RANGE_RE = re.compile(r"rows?\s+(\d+)\s*(?:-|–|to)\s*(\d+)", re.I)
# A sheet-closing annotation sitting alone in one cell ("--- End of bordereaux ---").
_FOOTER_RE = re.compile(r"\W*(end\s+of\b|\*{3}|-{3}|={3}|page\s+\d+|generated\b|prepared\s+by\b).*", re.I)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _classify_non_data_row(values: dict[str, Any]) -> dict[str, Any] | None:
    """Total/subtotal/footer rows are not policy transactions: they would be
    double counted downstream. Returns ``{"kind", "data_row_range"}`` or ``None``."""
    present = [v for v in values.values() if not _is_blank(v)]
    if len(present) == 1 and isinstance(present[0], str) and _FOOTER_RE.fullmatch(present[0].strip()):
        return {"kind": "FOOTER", "data_row_range": None}
    texts = [v.strip() for v in present if isinstance(v, str)]
    label = next((t for t in texts if _TOTAL_LABEL_RE.fullmatch(t)), None)
    if label is None or not any(try_parse_decimal(v)[1] for v in present if not isinstance(v, str) or v.strip() != label):
        return None
    kind = "GRAND_TOTAL" if label.lower().startswith("grand") else "SUBTOTAL" if label.lower().startswith("sub") else "TOTAL"
    span = next((m for t in texts if (m := _ROW_RANGE_RE.search(t))), None)
    return {"kind": kind, "data_row_range": [int(span.group(1)), int(span.group(2))] if span else None}


@dataclass
class CleaningOutcome:
    columns: list[str]
    rows: list[dict[str, Any]]
    before_row_count: int
    before_column_count: int
    after_row_count: int
    after_column_count: int
    transformations: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    total_rows: list[dict[str, Any]] = field(default_factory=list)
    """Total/subtotal/footer rows taken out of ``rows`` (kept for the Category F checks)."""


def clean_dataset(parsed: dict[str, Any]) -> CleaningOutcome:
    columns: list[str] = list(parsed["columns"])
    rows: list[dict[str, Any]] = [
        {"row_number": r["row_number"], "values": dict(r["values"])} for r in parsed["rows"]
    ]
    before_row_count = len(rows)
    before_column_count = len(columns)
    transformations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    # 1. Normalize column names (trim / collapse whitespace only - preserve meaning).
    renamed: dict[str, str] = {}
    new_columns: list[str] = []
    for col in columns:
        normalized = normalize_whitespace(col) if isinstance(col, str) else col
        if normalized != col:
            renamed[col] = normalized
        new_columns.append(normalized)
    if renamed:
        transformations.append({"type": "normalize_column_name", "renamed": renamed})
        for row in rows:
            for old, new in renamed.items():
                if old in row["values"]:
                    row["values"][new] = row["values"].pop(old)
    columns = new_columns

    # 2. Drop fully-blank columns.
    blank_columns = [c for c in columns if all(_is_blank(r["values"].get(c)) for r in rows)] if rows else []
    if blank_columns:
        transformations.append({"type": "drop_blank_column", "columns": blank_columns})
        columns = [c for c in columns if c not in blank_columns]
        for row in rows:
            for c in blank_columns:
                row["values"].pop(c, None)

    # 3. Drop fully-blank rows (no data at all after dropping blank columns).
    blank_row_numbers = [r["row_number"] for r in rows if all(_is_blank(v) for v in r["values"].values())]
    if blank_row_numbers:
        transformations.append(
            {
                "type": "drop_blank_row",
                "count": len(blank_row_numbers),
                "row_numbers": blank_row_numbers[:_MAX_LOGGED_ITEMS],
            }
        )
        rows = [r for r in rows if r["row_number"] not in set(blank_row_numbers)]

    # 3b. Total / subtotal / footer rows are not data: set them aside.
    total_rows: list[dict[str, Any]] = []
    data_rows: list[dict[str, Any]] = []
    for row in rows:
        kind = _classify_non_data_row(row["values"])
        if kind is None:
            data_rows.append(row)
        else:
            total_rows.append({**row, **kind})
    if total_rows:
        transformations.append(
            {
                "type": "separate_total_row",
                "count": len(total_rows),
                "rows": [{"row_number": r["row_number"], "kind": r["kind"]} for r in total_rows[:_MAX_LOGGED_ITEMS]],
            }
        )
        rows = data_rows

    # 4. Normalize null tokens ("N/A", "-", ...) to None.
    null_cells = 0
    for row in rows:
        for col, value in row["values"].items():
            if is_null_token(value):
                row["values"][col] = None
                null_cells += 1
    if null_cells:
        transformations.append({"type": "normalize_null_tokens", "cells_affected": null_cells})

    # 5. Normalize whitespace in remaining string values.
    ws_cells = 0
    for row in rows:
        for col, value in row["values"].items():
            if isinstance(value, str):
                normalized = normalize_whitespace(value)
                if normalized != value:
                    row["values"][col] = normalized
                    ws_cells += 1
    if ws_cells:
        transformations.append({"type": "normalize_whitespace", "cells_affected": ws_cells})

    # 6. Duplicate row detection (flag only - never remove).
    seen: dict[tuple, int] = {}
    dup_count = 0
    for row in rows:
        key = tuple(sorted(row["values"].items(), key=lambda kv: kv[0]))
        if key in seen:
            if dup_count < _MAX_LOGGED_ITEMS:
                warnings.append(
                    {"type": "duplicate_row", "row_number": row["row_number"], "duplicate_of": seen[key]}
                )
            dup_count += 1
        else:
            seen[key] = row["row_number"]

    # 7. Per-column numeric/date sniffing: normalize formatting, warn on
    # unparseable values within a column that is otherwise clearly typed.
    for col in columns:
        values = [(r["row_number"], r["values"].get(col)) for r in rows]
        non_blank = [(rn, v) for rn, v in values if not _is_blank(v)]
        if not non_blank:
            continue

        numeric_hits = sum(1 for _, v in non_blank if try_parse_decimal(v)[1])
        date_hits = sum(1 for _, v in non_blank if try_parse_date(v)[1] or looks_partial_date(v))
        numeric_ratio = numeric_hits / len(non_blank)
        date_ratio = date_hits / len(non_blank)

        if numeric_ratio >= _TYPE_SNIFF_THRESHOLD and numeric_ratio >= date_ratio:
            affected = 0
            # "1,234" is 1234 in one convention and 1.234 in another: the column's own
            # unambiguous values (391707,0 / 1,234.50 / 1.234.567) decide which.
            locale = detect_number_locale([v for _, v in non_blank])
            ambiguous = [(rn, v) for rn, v in non_blank if is_ambiguous_number(v)]
            if ambiguous and locale is not None:
                transformations.append(
                    {"type": "number_locale", "column": col, "locale": locale, "cells_affected": len(ambiguous)}
                )
            elif ambiguous:
                warnings.append(
                    {
                        "type": "ambiguous_number_format",
                        "column": col,
                        "count": len(ambiguous),
                        "examples": [str(v) for _, v in ambiguous[:3]],
                        "message": (
                            f"{len(ambiguous)} value(s) such as '{ambiguous[0][1]}' could be thousands or decimals "
                            "and nothing else in the column says which; read as thousands (1,234 = 1234)."
                        ),
                    }
                )
            for row in rows:
                raw = row["values"].get(col)
                if _is_blank(raw):
                    continue
                parsed, ok = try_parse_decimal(raw, locale)
                if ok:
                    canonical = format(parsed, "f")
                    if str(raw) != canonical:
                        row["values"][col] = canonical
                        affected += 1
                else:
                    if len([w for w in warnings if w.get("type") == "unparseable_numeric"]) < _MAX_LOGGED_ITEMS:
                        warnings.append(
                            {
                                "type": "unparseable_numeric",
                                "column": col,
                                "row_number": row["row_number"],
                                "value": raw,
                            }
                        )
            if affected:
                transformations.append({"type": "normalize_numeric_format", "column": col, "cells_affected": affected})
        elif date_ratio >= _TYPE_SNIFF_THRESHOLD:
            affected = 0
            partial_count = 0
            for row in rows:
                raw = row["values"].get(col)
                if _is_blank(raw):
                    continue
                parsed, ok = try_parse_date(raw)
                if ok:
                    iso = parsed.isoformat()
                    if str(raw) != iso:
                        row["values"][col] = iso
                        affected += 1
                elif (partial := try_parse_partial_date(raw)) is not None:
                    # Month + year only: kept (as YYYY-MM, never padded to a
                    # day it doesn't have) but flagged for the reviewer.
                    normalized = format_partial_date(*partial)
                    row["values"][col] = normalized
                    partial_count += 1
                    if partial_count <= _MAX_LOGGED_ITEMS:
                        warnings.append(
                            {
                                "type": "partial_date",
                                "column": col,
                                "row_number": row["row_number"],
                                "value": raw,
                                "normalized": normalized,
                                "precision": "MONTH",
                                "message": f"Date '{raw}' has no day; kept as {normalized} (month precision).",
                            }
                        )
                else:
                    if len([w for w in warnings if w.get("type") == "unparseable_date"]) < _MAX_LOGGED_ITEMS:
                        warnings.append(
                            {"type": "unparseable_date", "column": col, "row_number": row["row_number"], "value": raw}
                        )
            if affected:
                transformations.append({"type": "normalize_date_format", "column": col, "cells_affected": affected})
            if partial_count:
                transformations.append({"type": "normalize_partial_date", "column": col, "cells_affected": partial_count})
                warnings.append(
                    {
                        "type": "partial_date_summary",
                        "column": col,
                        "count": partial_count,
                        "message": f"{partial_count} date(s) have a month and year but no day; kept at month precision.",
                    }
                )

    if dup_count:
        warnings.append({"type": "duplicate_row_summary", "count": dup_count})

    return CleaningOutcome(
        columns=columns,
        rows=rows,
        before_row_count=before_row_count,
        before_column_count=before_column_count,
        after_row_count=len(rows),
        after_column_count=len(columns),
        transformations=transformations,
        warnings=warnings,
        total_rows=total_rows,
    )
