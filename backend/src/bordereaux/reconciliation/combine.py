"""Combine several tables (files / sheets, possibly different years and
quarters) into one standardised dataset.

Standardisation applied, in order: column names -> ``snake_case`` (+ confirmed
aliases), whitespace/null tokens, numbers -> canonical decimal strings, date
columns -> ISO ``YYYY-MM-DD`` (one format, so datasets are comparable), then
``_year`` / ``_quarter`` / ``_period`` derived from the period column.
Nothing is silently dropped: unparseable cells are kept as-is and counted.
"""

from __future__ import annotations

import re
from collections import Counter, OrderedDict
from datetime import date
from typing import Any

from bordereaux.cleaning.parsing import normalize_whitespace, try_parse_decimal
from bordereaux.reconciliation.schema import (
    DERIVED_COLUMNS,
    LINEAGE_COLUMNS,
    build_schema_summary,
    infer_type,
    is_blank,
    parse_date,
    slug,
)

_PERIOD_HINTS = ("period", "booking", "accounting", "posting", "transaction", "effective", "inception", "gl_date", "date")


def quarter_of(d: date) -> str:
    return f"Q{(d.month - 1) // 3 + 1}"


def _pick_period_column(date_cols: list[str], requested: str | None) -> str | None:
    if requested:
        return slug(requested) if slug(requested) in date_cols else None
    for hint in _PERIOD_HINTS:
        for c in date_cols:
            if hint in c:
                return c
    return date_cols[0] if date_cols else None


def combine_tables(
    tables: list[dict[str, Any]],
    aliases: dict[str, str] | None = None,
    period_column: str | None = None,
    day_first: bool = True,
    drop_cross_file_duplicates: bool = False,
) -> dict[str, Any]:
    """``tables``: [{"id", "file", "sheet", "columns", "rows"}] as read by
    ``readers``. Returns {"columns", "rows", "report"}."""
    summary = build_schema_summary(tables, aliases)
    alias_map = {slug(k): slug(v) for k, v in (aliases or {}).items()}

    def std(col: str) -> str:
        s = slug(col)
        return alias_map.get(s, s)

    columns: "OrderedDict[str, None]" = OrderedDict()
    for t in tables:
        for c in t["columns"]:
            columns.setdefault(std(c), None)
    data_cols = list(columns)

    # 1. Re-key every row onto the standard column names (first non-blank value
    # wins when two source columns were merged into one).
    rows: list[dict[str, Any]] = []
    for t in tables:
        for src in t["rows"]:
            out: dict[str, Any] = {c: None for c in data_cols}
            for original in t["columns"]:
                name = std(original)
                v = src.get(original)
                if isinstance(v, str):
                    v = normalize_whitespace(v)
                if is_blank(out[name]) and not is_blank(v):
                    out[name] = v
            out["_source_file"], out["_source_sheet"], out["_source_row"] = t["file"], t["sheet"], src.get("_source_row")
            rows.append(out)

    # 2. Column types over the combined data; normalise numbers and dates.
    col_types = {c: infer_type([r[c] for r in rows]) for c in data_cols}
    date_cols = [c for c, tp in col_types.items() if tp == "DATE"]
    bad_dates: Counter[str] = Counter()
    ambiguous_dates: Counter[str] = Counter()
    bad_numbers: Counter[str] = Counter()
    for r in rows:
        for c in data_cols:
            v = r[c]
            if is_blank(v):
                r[c] = None
                continue
            tp = col_types[c]
            if tp == "DATE":
                d, amb = parse_date(v, day_first)
                if d is None:
                    bad_dates[c] += 1
                else:
                    r[c] = d.isoformat()
                    if amb:
                        ambiguous_dates[c] += 1
            elif tp in ("DECIMAL", "INTEGER"):
                d, ok = try_parse_decimal(v)
                if ok:
                    r[c] = format(d, "f")
                else:
                    bad_numbers[c] += 1

    # 3. Optional de-duplication of identical rows that came from different files.
    duplicates = 0
    if len(tables) > 1:
        seen: dict[tuple, str] = {}
        kept = []
        for r in rows:
            key = tuple((c, r[c]) for c in data_cols)
            if key in seen and seen[key] != r["_source_file"]:
                duplicates += 1
                if drop_cross_file_duplicates:
                    continue
            else:
                seen.setdefault(key, r["_source_file"])
            kept.append(r)
        rows = kept

    # 4. Period columns.
    period_col = _pick_period_column(date_cols, period_column)
    undated = 0
    for r in rows:
        d = None
        if period_col and r.get(period_col):
            d = date.fromisoformat(r[period_col]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(r[period_col])) else None
        if d:
            r["_year"], r["_quarter"], r["_period"] = d.year, quarter_of(d), f"{d.year}-{quarter_of(d)}"
        else:
            r["_year"] = r["_quarter"] = r["_period"] = None
            undated += 1

    periods = Counter(r["_period"] for r in rows if r["_period"])
    by_file: dict[str, dict[str, Any]] = {}
    for r in rows:
        f = by_file.setdefault(r["_source_file"], {"file": r["_source_file"], "rows": 0, "periods": Counter()})
        f["rows"] += 1
        if r["_period"]:
            f["periods"][r["_period"]] += 1
    years = sorted({int(p[:4]) for p in periods})
    report = {
        "row_count": len(rows),
        "column_count": len(data_cols),
        "period_column": period_col,
        "date_columns": date_cols,
        "date_format": "YYYY-MM-DD",
        "day_first": day_first,
        "years": years,
        "quarters": [
            {"period": p, "year": int(p[:4]), "quarter": p[5:], "rows": n} for p, n in sorted(periods.items())
        ],
        "files": [
            {"file": f["file"], "rows": f["rows"], "periods": sorted(f["periods"])} for f in by_file.values()
        ],
        "rows_without_period": undated,
        "column_types": col_types,
        "unparsed_dates": dict(bad_dates),
        "ambiguous_dates": dict(ambiguous_dates),
        "unparsed_numbers": dict(bad_numbers),
        "cross_file_duplicate_rows": duplicates,
        "duplicates_removed": bool(drop_cross_file_duplicates and duplicates),
        "schema": summary,
        "warnings": _warnings(summary, bad_dates, ambiguous_dates, bad_numbers, duplicates, undated, period_col, day_first),
    }
    return {"columns": [*data_cols, *LINEAGE_COLUMNS, *DERIVED_COLUMNS], "rows": rows, "report": report}


def _warnings(summary, bad_dates, ambiguous, bad_numbers, duplicates, undated, period_col, day_first) -> list[str]:
    w: list[str] = []
    for c in summary["type_conflicts"]:
        w.append(f"Column '{c['column']}' has different types in different files: {c['types']}.")
    for c, n in bad_dates.items():
        w.append(f"{n} value(s) in date column '{c}' could not be parsed and were left unchanged.")
    for c, n in ambiguous.items():
        w.append(
            f"{n} date(s) in '{c}' are ambiguous (day and month both <= 12); read as "
            f"{'day-first' if day_first else 'month-first'}. Change the setting if that is wrong."
        )
    for c, n in bad_numbers.items():
        w.append(f"{n} value(s) in numeric column '{c}' could not be parsed and were left unchanged.")
    if duplicates:
        w.append(f"{duplicates} row(s) are identical to rows in another file (overlapping files?).")
    if period_col is None:
        w.append("No date column found to derive years/quarters from; choose a period column.")
    elif undated:
        w.append(f"{undated} row(s) have no usable date in '{period_col}' and carry no year/quarter.")
    return w
