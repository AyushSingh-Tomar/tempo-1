"""Category F - subtotal and total cross-check rules (§7).

Dataset-level, not per-row: these only apply when the file carries a
separate total/subtotal row. Used during Step 8 (financial checks) only -
there is nothing to check during mapping. If no total row is supplied the
caller simply does not call these (there is nothing to be "not applicable"
about at the per-row level, so this module has no RULES registry entry).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.rules import approx_equal
from bordereaux.money_rules.types import MoneyRole, MoneyRow


@dataclass(frozen=True)
class TotalsCheckResult:
    rule_id: str
    field: MoneyRole | None
    holds: bool
    computed_sum: Decimal | None
    total_row_value: Decimal | None
    message: str
    row_number: int | None = None
    """Source row of the total row the result is about."""


def check_column_totals(
    data_rows: list[MoneyRow],
    total_row: MoneyRow,
    config: MCRConfig,
    fields: tuple[MoneyRole, ...] = (
        MoneyRole.GROSS,
        MoneyRole.COMMISSION,
        MoneyRole.BROKERAGE,
        MoneyRole.TAX,
        MoneyRole.NET,
        MoneyRole.FINAL_NET,
    ),
) -> list[TotalsCheckResult]:
    """MCR-F1 / MCR-F3: for each field present in both the data rows and the
    total row, the sum of data-row values must equal the total-row value."""
    results: list[TotalsCheckResult] = []
    for field in fields:
        total_value = total_row.get(field)
        if total_value is None:
            continue
        values = [row.get(field) for row in data_rows if row.get(field) is not None]
        if not values:
            continue
        computed = sum(values, start=Decimal(0))
        holds = approx_equal(computed, total_value, config.tolerance)
        rule_id = "MCR-F1" if holds else "MCR-F3"
        results.append(
            TotalsCheckResult(
                rule_id=rule_id,
                field=field,
                holds=holds,
                computed_sum=computed,
                total_row_value=total_value,
                message=(
                    f"{field.value}: sum of data rows ({computed}) matches the total row ({total_value})."
                    if holds
                    else (
                        f"{field.value}: sum of data rows ({computed}) does not match the total row "
                        f"({total_value}) - possible missing/hidden rows or a parsing error."
                    )
                ),
            )
        )
    return results


def check_total_row_identity(total_row: MoneyRow, config: MCRConfig) -> TotalsCheckResult | None:
    """MCR-F2: the core deduction identity (G - C - T ~ N) must also hold on
    the aggregate (total) row, as a secondary confirmation."""
    if not total_row.has(MoneyRole.GROSS, MoneyRole.COMMISSION, MoneyRole.TAX, MoneyRole.NET):
        return None
    g, c, t, n = (total_row.get(r) for r in (MoneyRole.GROSS, MoneyRole.COMMISSION, MoneyRole.TAX, MoneyRole.NET))
    holds = approx_equal(g - c - t, n, config.tolerance)
    return TotalsCheckResult(
        rule_id="MCR-F2",
        field=None,
        holds=holds,
        computed_sum=g - c - t,
        total_row_value=n,
        message=(
            "Total row satisfies G - C - T = N."
            if holds
            else f"Total row fails G - C - T = N: {g} - {c} - {t} = {g - c - t}, expected {n}."
        ),
    )


@dataclass(frozen=True)
class TotalRow:
    row: MoneyRow
    kind: str  # TOTAL | SUBTOTAL | GRAND_TOTAL
    data_row_range: tuple[int, int] | None = None
    """1-based inclusive positions among the data rows when the label names them ("rows 1-15")."""


def evaluate_total_rows(data_rows: list[MoneyRow], totals: list[TotalRow], config: MCRConfig) -> list[TotalsCheckResult]:
    """Run F1/F3 (column sums) and F2 (identity) for every total row.

    A row that names its range is summed over exactly that range. A grand total
    in a file that also has subtotals may legitimately be the sum of the data
    rows, of the subtotals, or of everything above it - the reading that agrees
    with the most columns is used, so a correct total is never reported as wrong
    just because of how it was accumulated."""
    subtotals = [t.row for t in totals if t.kind == "SUBTOTAL"]
    results: list[TotalsCheckResult] = []
    for total in totals:
        if total.data_row_range:
            start, end = total.data_row_range
            scopes = [data_rows[max(start, 1) - 1 : end]]
        elif total.kind == "GRAND_TOTAL" and subtotals:
            scopes = [data_rows, subtotals, [*data_rows, *subtotals]]
        else:
            scopes = [data_rows]
        best = max((check_column_totals(scope, total.row, config) for scope in scopes), key=lambda rs: sum(r.holds for r in rs))
        results.extend(replace(r, row_number=total.row.row_number) for r in best)
        if (identity := check_total_row_identity(total.row, config)) is not None:
            results.append(replace(identity, row_number=total.row.row_number))
    return results
