"""Per-row rule tests, directly against the rule document's own worked
examples (Initial provided Info/Money-column-resolution-rules.docx)."""

from decimal import Decimal

import pytest

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.rules import RULE_CATEGORY, RULES, RuleOutcome, approx_equal, rule_g1, rule_g2, rule_g4
from bordereaux.money_rules.types import MoneyRole, MoneyRow, TreatyRates

R = MoneyRole
CFG = MCRConfig()


def D(x) -> Decimal:  # noqa: N802 - small local helper
    return Decimal(str(x))


def row(**values) -> MoneyRow:
    return MoneyRow(row_number=1, values={getattr(R, k): D(v) for k, v in values.items()})


def test_registry_consistency():
    assert set(RULES) == set(RULE_CATEGORY)
    assert len(RULES) == 18  # A1-5, B1-6, C1-4, G1,G2,G4


def test_approx_equal_tolerance():
    assert approx_equal(D("10000"), D("10050"), D("0.005")) is True  # 0.5% of 10050 ~ 50.25
    assert approx_equal(D("10000"), D("10100"), D("0.005")) is False  # 1% off
    assert approx_equal(D(0), D(0), D("0.005")) is True


# --- Category A: §2 worked example (G=10000, C=2500, T=1200, N=6300) -------


def test_a1_core_deduction_holds():
    r = row(GROSS=10000, COMMISSION=2500, TAX=1200, NET=6300)
    assert RULES["MCR-A1"](r, TreatyRates(), CFG) is RuleOutcome.HOLDS


def test_a1_fails_on_bad_net():
    r = row(GROSS=10000, COMMISSION=2500, TAX=1200, NET=6350)
    assert RULES["MCR-A1"](r, TreatyRates(), CFG) is RuleOutcome.FAILS


def test_a1_not_applicable_without_tax():
    r = row(GROSS=10000, COMMISSION=2500, NET=6300)
    assert RULES["MCR-A1"](r, TreatyRates(), CFG) is RuleOutcome.NOT_APPLICABLE


def test_a3_partial_net():
    # G - C = N (tax not yet deducted) - from §5.3's worked "Net" column.
    r = row(GROSS=10000, COMMISSION=2500, NET=7500)
    assert RULES["MCR-A3"](r, TreatyRates(), CFG) is RuleOutcome.HOLDS


def test_a4_build_up_cross_check():
    r = row(NET=6300, COMMISSION=2500, TAX=1200, GROSS=10000)
    assert RULES["MCR-A4"](r, TreatyRates(), CFG) is RuleOutcome.HOLDS


def test_a2_and_a5_final_net_chain():
    # G=10000, C=2500, B=100, T=1200 -> FN = 10000-2500-100-1200 = 6200
    r = row(GROSS=10000, COMMISSION=2500, BROKERAGE=100, TAX=1200, FINAL_NET=6200, NET=6300)
    assert RULES["MCR-A2"](r, TreatyRates(), CFG) is RuleOutcome.HOLDS
    assert RULES["MCR-A5"](r, TreatyRates(), CFG) is RuleOutcome.HOLDS  # N - B = 6300-100=6200=FN


# --- Category B: §3 worked example (comm%=25%, tax%=12%, G=10000) ---------


def test_b1_commission_ratio():
    r = row(GROSS=10000, COMMISSION=2500)
    treaty = TreatyRates(commission_pct=D("0.25"))
    assert RULES["MCR-B1"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_b3_tax_ratio():
    r = row(GROSS=10000, TAX=1200)
    treaty = TreatyRates(tax_pct=D("0.12"))
    assert RULES["MCR-B3"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_b_rules_not_applicable_without_rate():
    r = row(GROSS=10000, COMMISSION=2500)
    assert RULES["MCR-B1"](r, TreatyRates(), CFG) is RuleOutcome.NOT_APPLICABLE


def test_b_rules_exclude_zero_gross():
    r = row(GROSS=0, COMMISSION=0)
    treaty = TreatyRates(commission_pct=D("0.25"))
    assert RULES["MCR-B1"](r, treaty, CFG) is RuleOutcome.NOT_APPLICABLE


def test_b5_commission_on_ceded_basis():
    r = row(CEDED_PREMIUM=4000, COMMISSION=1000)
    treaty = TreatyRates(commission_pct=D("0.25"))
    assert RULES["MCR-B5"](r, treaty, CFG) is RuleOutcome.HOLDS


# --- Category C: §4 worked example ------------------------------------------
# Gross=100000 EUR, order%=20%, cess%=40%, fx=0.8511 (EUR->GBP)


def test_c1_order_share_alignment():
    r = row(GROSS=100000, OUR_SHARE=20000)
    treaty = TreatyRates(order_pct=D("0.20"))
    assert RULES["MCR-C1"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_c1_generalizes_to_commission_and_net():
    r = row(COMMISSION=2500, COMMISSION_OUR_SHARE=500, NET=7500, NET_OUR_SHARE=1500)
    treaty = TreatyRates(order_pct=D("0.20"))
    assert RULES["MCR-C1"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_c2_fx_settlement_alignment():
    r = row(OUR_SHARE=20000, SETTLEMENT=17021)
    treaty = TreatyRates(fx_rate=D("0.8511"))
    assert RULES["MCR-C2"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_c3_full_fx_and_share_chain():
    r = row(GROSS=100000, SETTLEMENT=17021)
    treaty = TreatyRates(order_pct=D("0.20"), fx_rate=D("0.8511"))
    assert RULES["MCR-C3"](r, treaty, CFG) is RuleOutcome.HOLDS


def test_c4_cession_and_order_chain():
    r = row(GROSS=100000, OUR_SHARE_OF_CEDED=8000)
    treaty = TreatyRates(cession_pct=D("0.40"), order_pct=D("0.20"))
    assert RULES["MCR-C4"](r, treaty, CFG) is RuleOutcome.HOLDS


# --- Category G: §8 worked example (cancellation row, all signs negative) -


def test_g4_net_sign_check_on_cancellation_row():
    r = row(GROSS=-10000, COMMISSION=-2500, TAX=-1200, NET=-6300)
    assert rule_g4(r, TreatyRates(), CFG) is RuleOutcome.HOLDS


def test_g4_not_applicable_on_positive_gross():
    r = row(GROSS=10000, COMMISSION=2500, TAX=1200, NET=6300)
    assert rule_g4(r, TreatyRates(), CFG) is RuleOutcome.NOT_APPLICABLE


def test_g1_sign_consistency_detects_mixed_signs():
    r = row(GROSS=-10000, COMMISSION=2500, TAX=-1200, NET=-6300)
    assert rule_g1(r, TreatyRates(), CFG) is RuleOutcome.FAILS


def test_g1_holds_when_all_negative():
    r = row(GROSS=-10000, COMMISSION=-2500, TAX=-1200, NET=-6300)
    assert rule_g1(r, TreatyRates(), CFG) is RuleOutcome.HOLDS


def test_g2_ratio_preserved_on_cancellation():
    r = row(GROSS=-10000, COMMISSION=-2500, TAX=-1200)
    treaty = TreatyRates(commission_pct=D("0.25"), tax_pct=D("0.12"))
    assert rule_g2(r, treaty, CFG) is RuleOutcome.HOLDS


def test_g2_not_applicable_on_positive_gross():
    r = row(GROSS=10000, COMMISSION=2500)
    treaty = TreatyRates(commission_pct=D("0.25"))
    assert rule_g2(r, treaty, CFG) is RuleOutcome.NOT_APPLICABLE


@pytest.mark.parametrize("rule_id", list(RULES))
def test_every_rule_is_not_applicable_on_empty_row(rule_id):
    r = MoneyRow(row_number=1, values={})
    assert RULES[rule_id](r, TreatyRates(), CFG) is RuleOutcome.NOT_APPLICABLE
