"""Settlement-currency conversion of the our-share amounts, using the treaty
step's per-currency FX rates (1 unit of the row currency = ``rate`` units of
the settlement currency). Adds columns; never alters the mapped values."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from bordereaux.treaty.derivation import rates_by_currency

_PREFERRED = ("gross_premium_our_share", "commission_our_share", "final_net_our_share")
_FALLBACK = ("gross_premium", "net_premium", "final_net_premium")
_CENT = Decimal("0.01")


def add_settlement_columns(
    fields: list[str],
    rows: list[dict[str, Any]],
    settlement_currency: str | None,
    fx_rates: list[dict[str, Any]] | None,
) -> tuple[list[str], list[dict[str, Any]]]:
    """Returns (fields, rows) with ``settlement_currency_applied``,
    ``fx_rate_applied`` and ``<field>_settlement`` columns appended. Rows whose
    currency has no rate get blanks rather than a guess."""
    rates = rates_by_currency(settlement_currency, fx_rates)
    if not rates or "original_currency" not in fields:
        return fields, rows
    sources = [f for f in _PREFERRED if f in fields] or [f for f in _FALLBACK if f in fields]
    new_fields = ["settlement_currency_applied", "fx_rate_applied", *[f"{f}_settlement" for f in sources]]
    out_rows: list[dict[str, Any]] = []
    for row in rows:
        ccy = str(row.get("original_currency") or "").strip().upper()
        rate = rates.get(ccy)
        extra: dict[str, Any] = {
            "settlement_currency_applied": settlement_currency if rate is not None else None,
            "fx_rate_applied": str(rate) if rate is not None else None,
        }
        for f in sources:
            try:
                val = Decimal(str(row.get(f))) if row.get(f) not in (None, "") else None
            except Exception:  # noqa: BLE001 - non-numeric cell stays blank
                val = None
            extra[f"{f}_settlement"] = (
                str((val * rate).quantize(_CENT, rounding=ROUND_HALF_UP)) if val is not None and rate is not None else None
            )
        out_rows.append({**row, **extra})
    return [*fields, *new_fields], out_rows
