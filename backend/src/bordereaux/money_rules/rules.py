"""Per-row MCR rules: Category A (core deduction), B (treaty-anchored ratio),
C (basis alignment) and G (sign/cancellation handling).

Category D (trap detection) and E (disambiguation/precedence) are
dataset/column-level and live in ``engine.score_candidate_meanings`` - they
decide what an *ambiguous* column means during mapping. Category F (totals)
is dataset-level and lives in ``totals.py``. Everything in this module is a
pure per-row boolean check used by both consumers: as evidence while scoring
a candidate mapping, and as a discrepancy check once mapping is final.

Rule doc reference: ``Initial provided Info/Money-column-resolution-rules.docx``.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Callable

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.types import MoneyRole, MoneyRow, TreatyRates

R = MoneyRole


class RuleOutcome(str, Enum):
    HOLDS = "HOLDS"
    FAILS = "FAILS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


RuleFn = Callable[[MoneyRow, TreatyRates, MCRConfig], RuleOutcome]


def approx_equal(left: Decimal, right: Decimal, tol: Decimal) -> bool:
    """|left - right| <= tol * max(|left|, |right|) - §1.4. Two exact zeros
    are equal; a zero compared against a nonzero value is never "close"."""
    if left == right:
        return True
    denom = max(abs(left), abs(right))
    if denom == 0:
        return True
    return abs(left - right) <= tol * denom


def _outcome(holds: bool) -> RuleOutcome:
    return RuleOutcome.HOLDS if holds else RuleOutcome.FAILS


# --------------------------------------------------------------------------
# Category A - core deduction relationships (§2)
# --------------------------------------------------------------------------


def rule_a1(row: MoneyRow, _treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """G - C - T ~ N."""
    if not row.has(R.GROSS, R.COMMISSION, R.TAX, R.NET):
        return RuleOutcome.NOT_APPLICABLE
    g, c, t, n = row.get(R.GROSS), row.get(R.COMMISSION), row.get(R.TAX), row.get(R.NET)
    return _outcome(approx_equal(g - c - t, n, cfg.tolerance))


def rule_a2(row: MoneyRow, _treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """G - C - B - T ~ FN."""
    if not row.has(R.GROSS, R.COMMISSION, R.BROKERAGE, R.TAX, R.FINAL_NET):
        return RuleOutcome.NOT_APPLICABLE
    g, c, b, t, fn = (row.get(x) for x in (R.GROSS, R.COMMISSION, R.BROKERAGE, R.TAX, R.FINAL_NET))
    return _outcome(approx_equal(g - c - b - t, fn, cfg.tolerance))


def rule_a3(row: MoneyRow, _treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """G - C ~ N (net of commission only - tax not yet deducted)."""
    if not row.has(R.GROSS, R.COMMISSION, R.NET):
        return RuleOutcome.NOT_APPLICABLE
    g, c, n = row.get(R.GROSS), row.get(R.COMMISSION), row.get(R.NET)
    return _outcome(approx_equal(g - c, n, cfg.tolerance))


def rule_a4(row: MoneyRow, _treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """N + C + T ~ G (build-up cross-check, mathematically equivalent to A1)."""
    if not row.has(R.NET, R.COMMISSION, R.TAX, R.GROSS):
        return RuleOutcome.NOT_APPLICABLE
    n, c, t, g = row.get(R.NET), row.get(R.COMMISSION), row.get(R.TAX), row.get(R.GROSS)
    return _outcome(approx_equal(n + c + t, g, cfg.tolerance))


def rule_a5(row: MoneyRow, _treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """N - B ~ FN."""
    if not row.has(R.NET, R.BROKERAGE, R.FINAL_NET):
        return RuleOutcome.NOT_APPLICABLE
    n, b, fn = row.get(R.NET), row.get(R.BROKERAGE), row.get(R.FINAL_NET)
    return _outcome(approx_equal(n - b, fn, cfg.tolerance))


# --------------------------------------------------------------------------
# Category B - treaty-anchored ratio relationships (§3)
# --------------------------------------------------------------------------


def _ratio_rule(base_role: MoneyRole, target_role: MoneyRole, rate_attr: str) -> RuleFn:
    def _rule(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
        rate = getattr(treaty, rate_attr)
        if rate is None or not row.has(base_role, target_role):
            return RuleOutcome.NOT_APPLICABLE
        base, target = row.get(base_role), row.get(target_role)
        if base == 0:
            # G3 exclusion guard: a ratio check against a zero base is meaningless,
            # not a failure.
            return RuleOutcome.NOT_APPLICABLE
        return _outcome(approx_equal(target, base * rate, cfg.tolerance))

    return _rule


rule_b1 = _ratio_rule(R.GROSS, R.COMMISSION, "commission_pct")
rule_b2 = _ratio_rule(R.GROSS, R.BROKERAGE, "brokerage_pct")
rule_b3 = _ratio_rule(R.GROSS, R.TAX, "tax_pct")
rule_b4 = _ratio_rule(R.GROSS, R.CEDED_PREMIUM, "cession_pct")
rule_b5 = _ratio_rule(R.CEDED_PREMIUM, R.COMMISSION, "commission_pct")
rule_b6 = _ratio_rule(R.CEDED_PREMIUM, R.TAX, "tax_pct")


# --------------------------------------------------------------------------
# Category C - basis alignment relationships (§4)
# --------------------------------------------------------------------------

_C1_PAIRS: list[tuple[MoneyRole, MoneyRole]] = [
    (R.GROSS, R.OUR_SHARE),
    (R.COMMISSION, R.COMMISSION_OUR_SHARE),
    (R.NET, R.NET_OUR_SHARE),
    (R.FINAL_NET, R.FINAL_NET_OUR_SHARE),
]


def rule_c1(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """our_share ~ full_value x order% - checked for every present full/share
    pair (gross, commission, net, final net - §4, "these rules apply to any
    money field, not just gross")."""
    if treaty.order_pct is None:
        return RuleOutcome.NOT_APPLICABLE
    applicable = [(f, s) for f, s in _C1_PAIRS if row.has(f, s)]
    if not applicable:
        return RuleOutcome.NOT_APPLICABLE
    checked = False
    for full_role, share_role in applicable:
        full_v, share_v = row.get(full_role), row.get(share_role)
        if full_v == 0:
            continue
        checked = True
        if not approx_equal(share_v, full_v * treaty.order_pct, cfg.tolerance):
            return RuleOutcome.FAILS
    return RuleOutcome.HOLDS if checked else RuleOutcome.NOT_APPLICABLE


def rule_c2(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """settlement ~ our_share x fx."""
    fx = row.fx_rate if row.fx_rate is not None else treaty.fx_rate
    if fx is None or not row.has(R.OUR_SHARE, R.SETTLEMENT):
        return RuleOutcome.NOT_APPLICABLE
    share, settlement = row.get(R.OUR_SHARE), row.get(R.SETTLEMENT)
    if share == 0:
        return RuleOutcome.NOT_APPLICABLE
    return _outcome(approx_equal(settlement, share * fx, cfg.tolerance))


def rule_c3(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """settlement ~ full_value x order% x fx (direct chain, no intermediate
    our-share column present)."""
    fx = row.fx_rate if row.fx_rate is not None else treaty.fx_rate
    if treaty.order_pct is None or fx is None or not row.has(R.GROSS, R.SETTLEMENT):
        return RuleOutcome.NOT_APPLICABLE
    gross, settlement = row.get(R.GROSS), row.get(R.SETTLEMENT)
    if gross == 0:
        return RuleOutcome.NOT_APPLICABLE
    return _outcome(approx_equal(settlement, gross * treaty.order_pct * fx, cfg.tolerance))


def rule_c4(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """our_share_of_ceded ~ gross x cess% x order%."""
    if treaty.cession_pct is None or treaty.order_pct is None or not row.has(R.GROSS, R.OUR_SHARE_OF_CEDED):
        return RuleOutcome.NOT_APPLICABLE
    gross, ours_of_ceded = row.get(R.GROSS), row.get(R.OUR_SHARE_OF_CEDED)
    if gross == 0:
        return RuleOutcome.NOT_APPLICABLE
    return _outcome(approx_equal(ours_of_ceded, gross * treaty.cession_pct * treaty.order_pct, cfg.tolerance))


# --------------------------------------------------------------------------
# Category G - sign and cancellation rules (§8)
# --------------------------------------------------------------------------

_PREMIUM_FLOW_ROLES = (R.GROSS, R.COMMISSION, R.BROKERAGE, R.TAX, R.NET, R.FINAL_NET)


def rule_g1(row: MoneyRow, _treaty: TreatyRates, _cfg: MCRConfig) -> RuleOutcome:
    """Sign consistency: on a cancellation row, every premium-flow value
    present should share the same sign (G3 excludes zeros from the check)."""
    nonzero = [row.get(role) for role in _PREMIUM_FLOW_ROLES if row.get(role) not in (None, Decimal(0))]
    if len(nonzero) < 2:
        return RuleOutcome.NOT_APPLICABLE
    signs = {v < 0 for v in nonzero}
    return _outcome(len(signs) == 1)


def rule_g2(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """Category B ratios must still hold on cancellation rows (signed
    arithmetic, no special-casing needed in the formulas themselves - this
    rule simply scopes B1-B4 to rows where gross is negative)."""
    gross = row.get(R.GROSS)
    if gross is None or gross >= 0:
        return RuleOutcome.NOT_APPLICABLE
    sub_rules = (rule_b1, rule_b2, rule_b3, rule_b4)
    outcomes = [r(row, treaty, cfg) for r in sub_rules]
    applicable = [o for o in outcomes if o != RuleOutcome.NOT_APPLICABLE]
    if not applicable:
        return RuleOutcome.NOT_APPLICABLE
    return _outcome(all(o == RuleOutcome.HOLDS for o in applicable))


def rule_g4(row: MoneyRow, treaty: TreatyRates, cfg: MCRConfig) -> RuleOutcome:
    """G - C - T ~ N must still hold, signs preserved, on cancellation rows
    (same identity as A1 - scoped to negative-gross rows for reporting)."""
    gross = row.get(R.GROSS)
    if gross is None or gross >= 0:
        return RuleOutcome.NOT_APPLICABLE
    return rule_a1(row, treaty, cfg)


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------

RULE_CATEGORY: dict[str, str] = {
    **{f"MCR-A{i}": "CORE_DEDUCTION" for i in range(1, 6)},
    **{f"MCR-B{i}": "TREATY_RATIO" for i in range(1, 7)},
    **{f"MCR-C{i}": "BASIS_ALIGNMENT" for i in range(1, 5)},
    "MCR-G1": "SIGN",
    "MCR-G2": "SIGN",
    "MCR-G4": "SIGN",
}

RULES: dict[str, RuleFn] = {
    "MCR-A1": rule_a1,
    "MCR-A2": rule_a2,
    "MCR-A3": rule_a3,
    "MCR-A4": rule_a4,
    "MCR-A5": rule_a5,
    "MCR-B1": rule_b1,
    "MCR-B2": rule_b2,
    "MCR-B3": rule_b3,
    "MCR-B4": rule_b4,
    "MCR-B5": rule_b5,
    "MCR-B6": rule_b6,
    "MCR-C1": rule_c1,
    "MCR-C2": rule_c2,
    "MCR-C3": rule_c3,
    "MCR-C4": rule_c4,
    "MCR-G1": rule_g1,
    "MCR-G2": rule_g2,
    "MCR-G4": rule_g4,
}

assert RULE_CATEGORY.keys() == RULES.keys()
