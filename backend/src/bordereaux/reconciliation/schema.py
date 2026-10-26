"""Column naming, type inference and the cross-file schema summary."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from rapidfuzz import fuzz

from bordereaux.cleaning.parsing import is_null_token, try_parse_decimal

_SLUG_RE = re.compile(r"[^a-z0-9]+")
LINEAGE_COLUMNS = ("_source_file", "_source_sheet", "_source_row")
DERIVED_COLUMNS = ("_year", "_quarter", "_period")
RESERVED = set(LINEAGE_COLUMNS) | set(DERIVED_COLUMNS)
_TYPE_THRESHOLD = 0.8
_DATE_FORMATS_DMY = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y"]
_DATE_FORMATS_MDY = ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", "%b %d, %Y", "%B %d, %Y"]
_DATE_FORMATS_ISO = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"]


def slug(name: str) -> str:
    """Standard column identifier: lower-case, ``snake_case`` ("Gross Prem." -> "gross_prem")."""
    plain = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")  # "Cédant" -> "Cedant"
    s = _SLUG_RE.sub("_", plain.strip().lower()).strip("_") or "column"
    return f"c_{s}" if s[0].isdigit() else s


def is_blank(v: Any) -> bool:
    return v is None or (isinstance(v, str) and (not v.strip() or is_null_token(v)))


def parse_date(value: Any, day_first: bool = True) -> tuple[date | None, bool]:
    """Returns ``(date, ambiguous)``. ``ambiguous`` = a slash/dash date whose
    day and month are both <= 12, so day-first vs month-first matters."""
    if isinstance(value, datetime):
        return value.date(), False
    if isinstance(value, date):
        return value, False
    if not isinstance(value, str):
        return None, False
    s = value.strip()
    if not s:
        return None, False
    for fmt in _DATE_FORMATS_ISO:
        try:
            return datetime.strptime(s, fmt).date(), False
        except ValueError:
            pass
    m = re.fullmatch(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})", s)
    ambiguous = bool(m and int(m.group(1)) <= 12 and int(m.group(2)) <= 12 and m.group(1) != m.group(2))
    order = (_DATE_FORMATS_DMY + _DATE_FORMATS_MDY) if day_first else (_DATE_FORMATS_MDY + _DATE_FORMATS_DMY)
    for fmt in order:
        try:
            return datetime.strptime(s, fmt).date(), ambiguous
        except ValueError:
            pass
    return None, False


def _looks_like_plain_number(v: Any) -> bool:
    if isinstance(v, (int, float, Decimal)) and not isinstance(v, bool):
        return True
    return isinstance(v, str) and bool(re.fullmatch(r"[+-]?\d+([.,]\d+)?", v.strip()))


def infer_type(values: list[Any]) -> str:
    """DATE | INTEGER | DECIMAL | STRING | EMPTY, from the non-blank values."""
    vals = [v for v in values if not is_blank(v)]
    if not vals:
        return "EMPTY"
    n = len(vals)
    date_hits = sum(1 for v in vals if (isinstance(v, (date, datetime))) or (isinstance(v, str) and not _looks_like_plain_number(v) and parse_date(v)[0]))
    if date_hits / n >= _TYPE_THRESHOLD:
        return "DATE"
    num = [try_parse_decimal(v) for v in vals if not isinstance(v, (date, datetime))]
    num_hits = [d for d, ok in num if ok]
    if len(num_hits) / n >= _TYPE_THRESHOLD:
        return "INTEGER" if all(d == d.to_integral_value() for d in num_hits) else "DECIMAL"
    return "STRING"


def _compatible(a: str, b: str) -> bool:
    if a == b or "EMPTY" in (a, b):
        return True
    return {a, b} <= {"INTEGER", "DECIMAL"}


def build_schema_summary(
    tables: list[dict[str, Any]], aliases: dict[str, str] | None = None
) -> dict[str, Any]:
    """``tables``: [{"id", "file", "sheet", "columns": [...], "rows": [...]}].
    ``aliases``: standard-column-name -> merged standard name (user-confirmed
    "these two columns are the same field").

    Returns the per-table schema, the columns every table has (``common``),
    the ones only some tables have (``partial``) and the ones in exactly one
    table (``unique``), type conflicts, and suggested merges."""
    aliases = {slug(k): slug(v) for k, v in (aliases or {}).items()}

    def std(col: str) -> str:
        s = slug(col)
        return aliases.get(s, s)

    per_table = []
    presence: dict[str, list[str]] = {}
    types: dict[str, dict[str, str]] = {}
    for t in tables:
        cols = []
        for original in t["columns"]:
            name = std(original)
            ctype = infer_type([r.get(original) for r in t["rows"]])
            filled = sum(1 for r in t["rows"] if not is_blank(r.get(original)))
            cols.append({"original": original, "standard": name, "type": ctype, "filled": filled, "total": len(t["rows"])})
            presence.setdefault(name, []).append(t["id"])
            types.setdefault(name, {})[t["id"]] = ctype
        per_table.append({"id": t["id"], "file": t["file"], "sheet": t["sheet"], "row_count": len(t["rows"]), "columns": cols})

    n_tables = len(tables)
    common = sorted(c for c, ids in presence.items() if len(set(ids)) == n_tables)
    unique = {c: ids[0] for c, ids in presence.items() if len(set(ids)) == 1 and n_tables > 1}
    partial = sorted(c for c, ids in presence.items() if 1 < len(set(ids)) < n_tables)
    conflicts = []
    for c, by_table in types.items():
        distinct = {tp for tp in by_table.values() if tp != "EMPTY"}
        if len(distinct) > 1 and not all(_compatible(a, b) for a in distinct for b in distinct):
            conflicts.append({"column": c, "types": by_table})

    suggestions = []
    singles = [(c, ids[0]) for c, ids in presence.items() if len(set(ids)) == 1]
    for i, (a, ta) in enumerate(singles):
        for b, tb in singles[i + 1 :]:
            if ta == tb:
                continue
            score = fuzz.ratio(a, b) / 100
            same_type = _compatible(types[a][ta], types[b][tb])
            if score >= 0.8 and same_type:
                suggestions.append({"columns": [a, b], "tables": [ta, tb], "score": round(score, 3)})

    return {
        "tables": per_table,
        "common_columns": common,
        "partial_columns": partial,
        "unique_columns": [{"column": c, "table": t} for c, t in sorted(unique.items())],
        "type_conflicts": conflicts,
        "suggested_merges": suggestions,
        "all_columns": sorted(presence),
    }
