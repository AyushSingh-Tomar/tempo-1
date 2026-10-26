from __future__ import annotations

from decimal import Decimal

import pytest

from bordereaux.mapping.money_resolution import resolve_unassigned_money_columns
from bordereaux.money_rules import MCRConfig, MoneyRole, TreatyRates

pytestmark = pytest.mark.unit


def test_resolves_pure_arithmetic_columns_with_no_name_signal():
    """Mirrors test_map_03_arithmetic_passthrough.xlsx's "Amount 1".."Amount 6"
    scenario: six money columns with zero semantic hint, resolvable via
    MCR-A1/A2/A3/A5 identities.

    Gross and net are structurally unique in the core-deduction identities
    (A1: G-C-T=N) and resolve unambiguously. Commission/tax are both simply
    subtracted from gross (A1/A2 are symmetric under swapping them), and
    brokerage/final_net form a second tied pair (A5: N-B=FN is symmetric
    under swapping those two) - both pairs are mathematically indistinguishable
    without a treaty-anchored ratio (Category B, not available until treaty
    figures are entered at Step 6), so a correct implementation must flag
    them ambiguous rather than guess (ADR-002 / rule-doc Category E)."""
    gross = [Decimal(g) for g in (100000, 200000, 150000, 175000, 225000, 300000)]
    commission = [g * Decimal("0.18") for g in gross]
    tax = [g * Decimal("0.12") for g in gross]
    brokerage = [g * Decimal("0.0175") for g in gross]
    net = [g - c - t for g, c, t in zip(gross, commission, tax)]
    final_net = [g - c - b - t for g, c, b, t in zip(gross, commission, brokerage, tax)]

    columns = {
        "Amount 1": gross,
        "Amount 2": commission,
        "Amount 3": net,
        "Amount 4": final_net,
        "Amount 5": tax,
        "Amount 6": brokerage,
    }
    roles = [MoneyRole.GROSS, MoneyRole.COMMISSION, MoneyRole.TAX, MoneyRole.BROKERAGE, MoneyRole.NET, MoneyRole.FINAL_NET]
    results = resolve_unassigned_money_columns(columns, {}, roles, TreatyRates(), MCRConfig())

    assert results["Amount 1"].resolved_role == MoneyRole.GROSS
    assert results["Amount 3"].resolved_role == MoneyRole.NET
    assert not results["Amount 1"].is_ambiguous
    assert not results["Amount 3"].is_ambiguous

    # Commission/tax are a tied pair; brokerage/final_net are a second tied
    # pair - both resolved to *some* role from their pair, both flagged.
    assert results["Amount 2"].is_ambiguous and results["Amount 5"].is_ambiguous
    assert {results["Amount 2"].resolved_role, results["Amount 5"].resolved_role} == {
        MoneyRole.COMMISSION,
        MoneyRole.TAX,
    }
    assert results["Amount 4"].is_ambiguous and results["Amount 6"].is_ambiguous
    assert {results["Amount 4"].resolved_role, results["Amount 6"].resolved_role} == {
        MoneyRole.BROKERAGE,
        MoneyRole.FINAL_NET,
    }


def test_returns_unresolved_when_no_arithmetic_signal():
    columns = {"Random A": [Decimal(1), Decimal(2), Decimal(3), Decimal(4), Decimal(5)]}
    results = resolve_unassigned_money_columns(columns, {}, [MoneyRole.GROSS], TreatyRates(), MCRConfig())
    assert results["Random A"].resolved_role is None
    assert results["Random A"].is_ambiguous is True


def test_empty_inputs_are_handled():
    assert resolve_unassigned_money_columns({}, {}, [MoneyRole.GROSS], TreatyRates(), MCRConfig()) == {}
    results = resolve_unassigned_money_columns({"A": [Decimal(1)] * 5}, {}, [], TreatyRates(), MCRConfig())
    assert results["A"].resolved_role is None
