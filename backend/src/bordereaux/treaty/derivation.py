"""Derive currencies and FX rates from the standardized (mapped) file so the
treaty-figures step can pre-fill them as "derived from file".

Pure Python, no AI. Rate convention: 1 unit of the row's currency =
``rate`` units of the settlement currency (the file's FX Rate column).
Everything derived here is a *suggestion*: the user can edit any value on the
treaty step and the submitted figures are what the checks use.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from typing import Any

CURRENCY_FIELD = "original_currency"
FX_FIELD = "fx_rate"
SETTLEMENT_FIELD = "settlement_currency"


def _norm_ccy(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    return text if len(text) == 3 and text.isalpha() else None


def _dec(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        d = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    return d if d > 0 else None


def derive_currency_rates(dataset: dict[str, Any]) -> dict[str, Any]:
    """``dataset`` is the standardized dataset (``{"fields": [...], "rows": [...]}``)."""
    fields = set(dataset.get("fields", []))
    rows = dataset.get("rows", [])
    if CURRENCY_FIELD not in fields:
        return {"currencies": [], "settlement_currency": None, "has_currency_column": False, "has_fx_column": FX_FIELD in fields}

    counts: Counter[str] = Counter()
    rates: dict[str, Counter[Decimal]] = {}
    settlement: Counter[str] = Counter()
    for row in rows:
        ccy = _norm_ccy(row.get(CURRENCY_FIELD))
        if ccy is None:
            continue
        counts[ccy] += 1
        rate = _dec(row.get(FX_FIELD)) if FX_FIELD in fields else None
        if rate is not None:
            rates.setdefault(ccy, Counter())[rate.normalize()] += 1
        s = _norm_ccy(row.get(SETTLEMENT_FIELD)) if SETTLEMENT_FIELD in fields else None
        if s:
            settlement[s] += 1

    settlement_currency = settlement.most_common(1)[0][0] if settlement else None
    if settlement_currency is None:
        # A currency whose rate is consistently 1 is the settlement currency.
        unit = [c for c, r in rates.items() if set(r) == {Decimal(1)}]
        if len(unit) == 1:
            settlement_currency = unit[0]

    currencies = []
    for ccy, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        seen = rates.get(ccy)
        entry: dict[str, Any] = {
            "currency": ccy,
            "row_count": n,
            "rate": None,
            "source": "FILE" if seen else None,
            "conflicting_rates": [],
        }
        if seen:
            ordered = [r for r, _ in seen.most_common()]
            entry["rate"] = str(ordered[0])
            if len(ordered) > 1:
                entry["conflicting_rates"] = [str(r) for r in ordered]
        if ccy == settlement_currency and entry["rate"] is None:
            entry["rate"], entry["source"] = "1", "FILE"
        currencies.append(entry)

    return {
        "currencies": currencies,
        "settlement_currency": settlement_currency,
        "has_currency_column": True,
        "has_fx_column": FX_FIELD in fields,
    }


def rates_by_currency(settlement_currency: str | None, fx_rates: list[dict[str, Any]] | None) -> dict[str, Decimal]:
    """currency -> rate into the settlement currency (settlement currency itself = 1)."""
    out: dict[str, Decimal] = {}
    for entry in fx_rates or []:
        ccy = _norm_ccy(entry.get("currency"))
        rate = _dec(entry.get("rate"))
        if ccy and rate:
            out[ccy] = rate
    if settlement_currency:
        out.setdefault(settlement_currency.upper(), Decimal(1))
    return out


# --- Treaty percentages --------------------------------------------------------

# figure -> per-row canonical field that carries it when the dictionary maps one
_PCT_FIELDS: dict[str, str | None] = {
    "commission_pct": "commission_pct",
    "brokerage_pct": "brokerage_pct",
    "tax_pct": None,
    "cession_pct": None,
    "order_pct": "order_pct",
}
_TREATY_FIELD_FOR = {
    "commission_pct": "treaty_commission_pct",
    "brokerage_pct": "treaty_brokerage_pct",
    "tax_pct": "treaty_tax_pct",
    "cession_pct": "treaty_cession_pct",
    "order_pct": "treaty_order_pct",
}
_MAX_EXAMPLE_ROWS = 8


def _alias_sets() -> dict[str, set[str]]:
    from bordereaux.mapping.aliasing import normalize_alias
    from bordereaux.schemas.loader import load_schema_definition

    by_name = {f["name"]: f for f in load_schema_definition()["fields"]}
    out: dict[str, set[str]] = {}
    for figure, tname in _TREATY_FIELD_FOR.items():
        f = by_name.get(tname, {})
        aliases = {normalize_alias(a) for a in f.get("aliases", [])}
        aliases.add(normalize_alias(f.get("display_name", "")))
        out[figure] = {a for a in aliases if a}
    return out


def _to_fraction(values: list[Decimal]) -> list[Decimal]:
    """Files carry percentages as 25 or as 0.25. If anything exceeds 1 the
    column is in whole percent; otherwise it is already a fraction."""
    if any(v > 1 for v in values):
        return [v / 100 for v in values]
    return values


def derive_treaty_percentages(dataset: dict[str, Any], extra_sources: dict[str, str]) -> list[dict[str, Any]]:
    """For each of the five treaty percentages, look for a per-row column in the
    mapped file. ``extra_sources`` maps every mapped target field to its original
    source header (used for labelling, and to recognise pass-through ``extra_x``
    columns by their treaty aliases), so columns the dictionary does not map
    (Cession %, Tax %) can still be recognised by their treaty aliases.

    Status per figure: ``UNIFORM`` (same on every filled row - safe to
    pre-fill), ``VARIES`` (differs between rows - alert, most common value
    pre-filled), ``NOT_FOUND`` (no such column)."""
    from bordereaux.mapping.aliasing import normalize_alias

    fields = list(dataset.get("fields", []))
    rows = dataset.get("rows", [])
    aliases = _alias_sets()
    results: list[dict[str, Any]] = []
    for figure, canonical in _PCT_FIELDS.items():
        column = canonical if canonical in fields else None
        source_header = extra_sources.get(column) if column else None
        if column is None:
            for target, header in extra_sources.items():
                if target.startswith("extra_") and target in fields and normalize_alias(header) in aliases[figure]:
                    column, source_header = target, header
                    break
        entry: dict[str, Any] = {
            "figure": figure,
            "status": "NOT_FOUND",
            "source_column": source_header or column,
            "value": None,
            "filled_rows": 0,
            "total_rows": len(rows),
            "distinct": [],
            "example_rows": [],
        }
        if column is None:
            results.append(entry)
            continue
        parsed: list[tuple[int, Decimal]] = []
        for row in rows:
            d = _dec_any(row.get(column))
            if d is not None:
                parsed.append((row.get("_source_row_number"), d))
        if not parsed:
            results.append(entry)
            continue
        fractions = _to_fraction([d for _, d in parsed])
        counts: Counter[Decimal] = Counter(f.normalize() for f in fractions)
        ordered = counts.most_common()
        top = ordered[0][0]
        entry.update(
            status="UNIFORM" if len(ordered) == 1 else "VARIES",
            value=str(top),
            filled_rows=len(parsed),
            distinct=[{"value": str(v), "row_count": n} for v, n in ordered],
            example_rows=[n for (n, _), f in zip(parsed, fractions) if f.normalize() != top][:_MAX_EXAMPLE_ROWS],
        )
        results.append(entry)
    return results


def _dec_any(value: Any) -> Decimal | None:
    """Like ``_dec`` but allows zero (a 0% brokerage is a real value)."""
    if value in (None, ""):
        return None
    try:
        d = Decimal(str(value).strip().rstrip("%"))
    except (InvalidOperation, ValueError):
        return None
    return d if d >= 0 else None
