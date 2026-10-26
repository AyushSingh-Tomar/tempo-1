"""Shared value types for the MCR engine.

All money/rate values are ``Decimal``. Treaty rates are **fractions**, not
percentages: 25% is ``Decimal("0.25")``, not ``Decimal("25")``. Converting a
user-entered "25.00%" string into that fraction is the API/validation layer's
job (outside this engine), not this module's.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Optional


class MoneyRole(str, Enum):
    """Canonical premium-flow roles a resolved money column can play.

    These are the symbols used throughout the rule document (§1.3):
    G=gross, C=commission, B=brokerage, T=tax, N=net, FN=final_net,
    CP=ceded_premium. Plus the basis-alignment roles from Category C.
    """

    GROSS = "G"
    COMMISSION = "C"
    BROKERAGE = "B"
    TAX = "T"
    NET = "N"
    FINAL_NET = "FN"
    CEDED_PREMIUM = "CP"
    SUM_INSURED = "SI"
    OUR_SHARE = "OUR_SHARE"  # gross x order%  (e.g. "GWP Our Share")
    SETTLEMENT = "SETTLEMENT"  # our_share x fx
    OUR_SHARE_OF_CEDED = "OUR_SHARE_OF_CEDED"  # gross x cess% x order%
    COMMISSION_OUR_SHARE = "COMMISSION_OUR_SHARE"
    NET_OUR_SHARE = "NET_OUR_SHARE"
    FINAL_NET_OUR_SHARE = "FINAL_NET_OUR_SHARE"


@dataclass
class MoneyRow:
    """One bordereaux row's resolved money fields, by role. Any role may be
    ``None`` if that column isn't present/mapped in this file - rules whose
    required inputs are missing report ``NOT_APPLICABLE``, never a guess."""

    row_number: int
    values: dict[MoneyRole, Optional[Decimal]]
    fx_rate: Optional[Decimal] = None
    """Rate into the settlement currency for *this row's* currency (multi-currency
    files); falls back to ``TreatyRates.fx_rate`` when ``None``."""

    def get(self, role: MoneyRole) -> Optional[Decimal]:
        return self.values.get(role)

    def has(self, *roles: MoneyRole) -> bool:
        return all(self.values.get(r) is not None for r in roles)


@dataclass(frozen=True)
class TreatyRates:
    """The 6 Group-J treaty figures, as fractions (see module docstring)."""

    commission_pct: Optional[Decimal] = None
    brokerage_pct: Optional[Decimal] = None
    tax_pct: Optional[Decimal] = None
    cession_pct: Optional[Decimal] = None
    order_pct: Optional[Decimal] = None
    fx_rate: Optional[Decimal] = None
    expected_si_rate: Optional[Decimal] = None
    """Optional technical premium rate on sum insured (fraction); enables MCR-D1."""


@dataclass(frozen=True)
class RuleResult:
    """One rule's evaluation across a dataset."""

    rule_id: str
    category: str
    evaluated_rows: int
    passed_rows: int
    excluded_rows: int
    row_agreement: Decimal
    in_effect: bool
    """True once ``row_agreement >= config.row_agreement_threshold`` AND
    ``evaluated_rows >= config.min_rows_for_resolution``."""
    failing_row_numbers: list[int]
