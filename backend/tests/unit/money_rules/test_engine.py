"""Dataset-level engine tests: row-agreement/discrepancy generation (Step 8),
totals cross-checks (Category F), trap detection (Category D) and candidate
disambiguation (Category E) - against the rule document's worked examples."""

from decimal import Decimal

import pytest

from bordereaux.money_rules.config import MCRConfig
from bordereaux.money_rules.engine import (
    detect_ambiguous_net,
    detect_commission_bundles_brokerage,
    detect_gross_is_ceded,
    detect_our_share_mislabelled,
    evaluate_dataset,
    find_discrepancies,
    is_ambiguous,
    rank_candidate_roles,
)
from bordereaux.money_rules.totals import TotalRow, check_column_totals, check_total_row_identity, evaluate_total_rows
from bordereaux.money_rules.types import MoneyRole, MoneyRow, TreatyRates

R = MoneyRole
CFG = MCRConfig()


def D(x) -> Decimal:  # noqa: N802
    return Decimal(str(x))


def honest_row(n: int) -> MoneyRow:
    return MoneyRow(n, {R.GROSS: D(10000), R.COMMISSION: D(2500), R.TAX: D(1200), R.NET: D(6300)})


TREATY = TreatyRates(commission_pct=D("0.25"), tax_pct=D("0.12"))


def test_evaluate_dataset_in_effect_when_row_agreement_sufficient():
    rows = [honest_row(i) for i in range(1, 21)]  # 20 honest rows
    evaluation = evaluate_dataset(rows, TREATY, CFG)
    assert evaluation.rule_results["MCR-A1"].in_effect is True
    assert evaluation.rule_results["MCR-A1"].row_agreement == D(1)
    assert evaluation.rule_results["MCR-A1"].failing_row_numbers == []


def test_find_discrepancies_flags_only_the_outlier_row():
    # 20 honest rows + 1 row with a keying error only in Net (C and T still
    # satisfy the treaty ratios, so B1/B3 remain intact for that row too).
    rows = [honest_row(i) for i in range(1, 21)]
    bad = MoneyRow(21, {R.GROSS: D(10000), R.COMMISSION: D(2500), R.TAX: D(1200), R.NET: D(6350)})
    rows.append(bad)

    evaluation = evaluate_dataset(rows, TREATY, CFG)
    assert evaluation.rule_results["MCR-A1"].in_effect is True  # 20/21 ~ 95.2% >= 90%
    assert evaluation.rule_results["MCR-B1"].failing_row_numbers == []
    assert evaluation.rule_results["MCR-B3"].failing_row_numbers == []

    discrepancies = find_discrepancies(rows, TREATY, CFG, evaluation)
    a1_findings = [d for d in discrepancies if d.rule_id == "MCR-A1"]
    assert [d.row_number for d in a1_findings] == [21]
    assert a1_findings[0].category == "CORE_DEDUCTION"
    assert a1_findings[0].expected_value == D(6300)
    assert a1_findings[0].observed_value == D(6350)
    assert a1_findings[0].variance == D(50)
    # Only the one broken identity should surface - not a cascade of
    # unrelated findings for the same row.
    assert not any(d.rule_id in ("MCR-B1", "MCR-B3") and d.row_number == 21 for d in discrepancies)


def test_rule_not_in_effect_below_min_rows_produces_no_discrepancies():
    # 3 rows, one of which fails A1 - too few rows to trust the rule at all.
    rows = [honest_row(1), honest_row(2), MoneyRow(3, {R.GROSS: D(10000), R.COMMISSION: D(2500), R.TAX: D(1200), R.NET: D(1)})]
    evaluation = evaluate_dataset(rows, TREATY, CFG)
    assert evaluation.rule_results["MCR-A1"].in_effect is False
    assert find_discrepancies(rows, TREATY, CFG, evaluation) == []


# --- Category F: totals (§7) -----------------------------------------------


def test_f1_column_totals_match():
    data_rows = [MoneyRow(i, {R.GROSS: D(100)}) for i in range(1, 101)]  # 100 x 100 = 10000
    total_row = MoneyRow(0, {R.GROSS: D(10000)})
    results = check_column_totals(data_rows, total_row, CFG)
    assert results[0].rule_id == "MCR-F1"
    assert results[0].holds is True


def test_f3_column_totals_mismatch():
    data_rows = [MoneyRow(i, {R.GROSS: D("152470")}) for i in range(1, 101)]  # sums to 15,247,000
    total_row = MoneyRow(0, {R.GROSS: D("14890000")})  # mismatched total
    results = check_column_totals(data_rows, total_row, CFG)
    assert results[0].rule_id == "MCR-F3"
    assert results[0].holds is False
    assert results[0].computed_sum == D("15247000")


def test_f2_total_row_identity():
    total_row = MoneyRow(0, {R.GROSS: D("15247000"), R.COMMISSION: D("3811750"), R.TAX: D("1829640"), R.NET: D("9605610")})
    result = check_total_row_identity(total_row, CFG)
    assert result is not None
    assert result.rule_id == "MCR-F2"
    assert result.holds is True


def _flow_row(n: int, gross: int) -> MoneyRow:
    return MoneyRow(n, {R.GROSS: D(gross), R.COMMISSION: D(gross) / 4, R.TAX: D(gross) * D("0.12"), R.NET: D(gross) * D("0.63")})


def _total(n: int, gross: int, **kw) -> TotalRow:
    return TotalRow(row=_flow_row(n, gross), **kw)


def test_total_row_sums_all_data_rows_and_checks_the_identity():
    data = [_flow_row(i, 1000) for i in range(1, 5)]
    results = evaluate_total_rows(data, [_total(99, 4000, kind="TOTAL")], CFG)
    assert all(r.holds and r.row_number == 99 for r in results)
    assert {r.rule_id for r in results} == {"MCR-F1", "MCR-F2"}


def test_total_row_that_does_not_add_up_raises_f3():
    data = [_flow_row(i, 1000) for i in range(1, 5)]
    results = evaluate_total_rows(data, [_total(99, 3500, kind="TOTAL")], CFG)
    assert {r.rule_id for r in results if not r.holds} == {"MCR-F3"}


def test_subtotal_that_names_its_rows_is_summed_over_exactly_those_rows():
    data = [_flow_row(i, 1000 * i) for i in range(1, 5)]  # 1000, 2000, 3000, 4000
    results = evaluate_total_rows(data, [_total(98, 3000, kind="SUBTOTAL", data_row_range=(1, 2))], CFG)
    assert all(r.holds for r in results)
    wrong = evaluate_total_rows(data, [_total(98, 3000, kind="SUBTOTAL", data_row_range=(1, 3))], CFG)
    assert any(r.rule_id == "MCR-F3" for r in wrong)


@pytest.mark.parametrize("grand", [10000 + 3000, 3000, 10000])
def test_grand_total_may_cover_the_data_rows_the_subtotals_or_everything_above(grand):
    data = [_flow_row(i, 1000 * i) for i in range(1, 5)]  # 10000 in all
    subtotal = _total(98, 3000, kind="SUBTOTAL", data_row_range=(1, 2))
    results = evaluate_total_rows(data, [subtotal, _total(99, grand, kind="GRAND_TOTAL")], CFG)
    assert all(r.holds for r in results), [r.message for r in results if not r.holds]
    bad = evaluate_total_rows(data, [subtotal, _total(99, 7777, kind="GRAND_TOTAL")], CFG)
    assert any(r.rule_id == "MCR-F3" and r.row_number == 99 for r in bad)


# --- Category D: trap detection (§5) ----------------------------------------


def test_d1_gross_is_actually_ceded():
    # §5.1 worked example, replicated across enough rows to clear the
    # min_rows_for_resolution gate.
    n = 6
    candidate_values = [D(4000)] * n  # the mislabelled "Gross Premium" column
    implied_gross = [D(10000)] * n
    commission_values = [D(1000)] * n
    treaty = TreatyRates(cession_pct=D("0.40"), commission_pct=D("0.25"))
    result = detect_gross_is_ceded(candidate_values, implied_gross, commission_values, treaty, CFG)
    assert result.detected is True
    assert result.resolved_role is R.CEDED_PREMIUM


def test_d1_not_detected_for_a_genuine_gross_column():
    n = 6
    candidate_values = [D(10000)] * n
    implied_gross = [D(10000)] * n
    treaty = TreatyRates(cession_pct=D("0.40"), commission_pct=D("0.25"))
    result = detect_gross_is_ceded(candidate_values, implied_gross, None, treaty, CFG)
    assert result.detected is False


def test_d2_commission_bundles_brokerage():
    # Clean numeric case from §5.2: comm%=25%, brok%=5%, combined 30%,
    # Gross=10000 -> bundled column = 3000.
    n = 6
    candidate_values = [D(3000)] * n
    gross_values = [D(10000)] * n
    treaty = TreatyRates(commission_pct=D("0.25"), brokerage_pct=D("0.05"))
    result = detect_commission_bundles_brokerage(candidate_values, gross_values, treaty, CFG)
    assert result.detected is True


def test_d3_distinguishes_partial_from_true_net():
    # §5.3 worked example: Net=7500 (partial), NetDue=6300 (true net).
    n = 6
    gross = [D(10000)] * n
    comm = [D(2500)] * n
    tax = [D(1200)] * n

    partial_net = detect_ambiguous_net([D(7500)] * n, gross, comm, tax, CFG)
    assert partial_net.detected is True
    assert "net-of-commission-only" in partial_net.message

    true_net = detect_ambiguous_net([D(6300)] * n, gross, comm, tax, CFG)
    assert true_net.detected is True
    assert "true net premium" in true_net.message


def test_d3_genuinely_ambiguous_when_tax_is_zero():
    # If tax is uniformly zero, A1 and A3 coincide - must flag, not guess.
    n = 6
    gross = [D(10000)] * n
    comm = [D(2500)] * n
    tax = [D(0)] * n
    result = detect_ambiguous_net([D(7500)] * n, gross, comm, tax, CFG)
    assert result.detected is False


def test_d5_our_share_mislabelled_as_100_percent():
    n = 6
    candidate_values = [D(20000)] * n  # labelled "GWP (100%)"
    true_gross = [D(100000)] * n
    treaty = TreatyRates(order_pct=D("0.20"))
    result = detect_our_share_mislabelled(candidate_values, true_gross, treaty, CFG)
    assert result.detected is True
    assert result.resolved_role is R.OUR_SHARE


# --- Category E: disambiguation / precedence (§6) ---------------------------


def test_rank_candidate_roles_prefers_higher_row_agreement():
    rows = [honest_row(i) for i in range(1, 21)]
    ranked = rank_candidate_roles(rows, [R.COMMISSION, R.TAX], TREATY, CFG)
    assert ranked[0].best_row_agreement >= ranked[1].best_row_agreement


def test_is_ambiguous_flags_close_scores():
    rows = [honest_row(i) for i in range(1, 21)]
    ranked = rank_candidate_roles(rows, [R.COMMISSION, R.TAX], TREATY, CFG)
    # Both roles are fully corroborated in this fixture (both 100% row
    # agreement) - margin is 0, which is <= the configured 5% margin.
    assert is_ambiguous(ranked, CFG) is True


def test_is_ambiguous_false_for_single_candidate():
    rows = [honest_row(i) for i in range(1, 21)]
    ranked = rank_candidate_roles(rows, [R.COMMISSION], TREATY, CFG)
    assert is_ambiguous(ranked, CFG) is False
