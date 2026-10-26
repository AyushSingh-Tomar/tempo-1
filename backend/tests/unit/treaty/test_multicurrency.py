from decimal import Decimal as D

import pytest

from bordereaux.money_rules import MCRConfig, MoneyRole as R, MoneyRow, TreatyRates
from bordereaux.money_rules.traps import detect_bundled_commission, detect_gross_is_ceded_rows
from bordereaux.treaty.derivation import derive_currency_rates, rates_by_currency
from bordereaux.treaty.schemas import TreatyFiguresRequest
from bordereaux.treaty.settlement import add_settlement_columns

pytestmark = pytest.mark.unit
TREATY = TreatyRates(commission_pct=D("0.25"), brokerage_pct=D("0.0125"), tax_pct=D("0.12"), cession_pct=D("0.4"))


def test_derive_rates_and_settlement_currency():
    ds = {
        "fields": ["original_currency", "fx_rate"],
        "rows": [
            {"original_currency": "eur", "fx_rate": "1.0"},
            {"original_currency": "EUR", "fx_rate": "1"},
            {"original_currency": "GBP", "fx_rate": "1.175"},
            {"original_currency": "GBP", "fx_rate": "1.2"},
            {"original_currency": "XX", "fx_rate": "9"},
        ],
    }
    out = derive_currency_rates(ds)
    by = {c["currency"]: c for c in out["currencies"]}
    assert out["settlement_currency"] == "EUR"
    assert by["EUR"]["rate"] == "1" and by["GBP"]["conflicting_rates"] == ["1.175", "1.2"]
    assert "XX" not in by


def test_no_currency_column_means_nothing_derived():
    assert derive_currency_rates({"fields": ["umr"], "rows": []})["currencies"] == []


def test_request_validation():
    base = {"commission_pct": "0.25", "tax_pct": "0.1", "cession_pct": "0.4"}
    TreatyFiguresRequest(**base, settlement_currency="eur", fx_rates=[{"currency": "gbp", "rate": "1.1"}])
    with pytest.raises(ValueError):
        TreatyFiguresRequest(**base, fx_rates=[{"currency": "GBP", "rate": "0"}])
    with pytest.raises(ValueError):
        TreatyFiguresRequest(**base, fx_rates=[{"currency": "GBP", "rate": "1"}, {"currency": "gbp", "rate": "2"}])


def test_settlement_columns_apply_per_currency_rate():
    fields, rows = add_settlement_columns(
        ["original_currency", "gross_premium_our_share"],
        [
            {"original_currency": "GBP", "gross_premium_our_share": "100"},
            {"original_currency": "JPY", "gross_premium_our_share": "100"},
        ],
        "EUR",
        [{"currency": "GBP", "rate": "1.175"}],
    )
    assert "gross_premium_our_share_settlement" in fields
    assert rows[0]["gross_premium_our_share_settlement"] == "117.50" and rows[0]["fx_rate_applied"] == "1.175"
    assert rows[1]["gross_premium_our_share_settlement"] is None  # no rate -> blank, never a guess
    assert rates_by_currency("EUR", None) == {"EUR": D(1)}


def test_bundled_commission_detected_only_on_affected_row():
    clean = MoneyRow(1, {R.GROSS: D(1000), R.COMMISSION: D(250), R.BROKERAGE: D("12.5")})
    bundled = MoneyRow(2, {R.GROSS: D(750), R.COMMISSION: D(250), R.BROKERAGE: D("12.5")})
    cfg = MCRConfig()
    assert detect_bundled_commission(clean, TREATY, cfg) is None
    trap = detect_bundled_commission(bundled, TREATY, cfg)
    assert trap and trap.rule_id == "MCR-D2" and "brokerage" in trap.evidence["corroborated_by"]


def test_gross_is_ceded_needs_peer_evidence():
    rows, si, groups = [], {}, {}
    for i in range(1, 8):  # honest rows: premium = 2% of sum insured
        rows.append(MoneyRow(i, {R.GROSS: D(20000), R.COMMISSION: D(5000)}))
        si[i], groups[i] = D(1_000_000), "marine"
    rows.append(MoneyRow(8, {R.GROSS: D(8000), R.COMMISSION: D(2000)}))  # 40% of the peer figure
    si[8], groups[8] = D(1_000_000), "marine"
    traps = detect_gross_is_ceded_rows(rows, si, groups, TREATY, MCRConfig())
    assert [t.row_number for t in traps] == [8] and traps[0].rule_id == "MCR-D1"
    # Too few peers -> no verdict.
    assert detect_gross_is_ceded_rows(rows[:3], si, groups, TREATY, MCRConfig()) == []


def test_gross_is_ceded_never_flags_a_row_whose_own_deduction_identity_holds():
    """Rule doc §5.1 signal 3: a ceded "gross" cannot satisfy G - C - T = N on a full-value basis."""
    def full(i, gross):
        return MoneyRow(i, {R.GROSS: D(gross), R.COMMISSION: D(gross) * D("0.25"), R.TAX: D(gross) * D("0.12"), R.NET: D(gross) * D("0.63")})

    rows = [full(i, 20000) for i in range(1, 8)]
    rows.append(full(8, 8000))  # 40% of the peer figure, but every identity holds -> honest
    si = {i: D(1_000_000) for i in range(1, 9)}
    groups = {i: "marine" for i in si}
    assert detect_gross_is_ceded_rows(rows, si, groups, TREATY, MCRConfig()) == []
    rows[7] = MoneyRow(8, {R.GROSS: D(8000), R.COMMISSION: D(2000), R.TAX: D(960), R.NET: D(8000)})  # identity broken
    assert [t.row_number for t in detect_gross_is_ceded_rows(rows, si, groups, TREATY, MCRConfig())] == [8]


def test_treaty_percentages_uniform_varying_and_missing():
    from bordereaux.treaty.derivation import derive_treaty_percentages

    rows = [
        {"_source_row_number": i + 2, "commission_pct": "25", "brokerage_pct": "1.25" if i < 8 else "2", "extra_cession": "0.4"}
        for i in range(10)
    ]
    ds = {"fields": ["commission_pct", "brokerage_pct", "extra_cession"], "rows": rows}
    out = {f["figure"]: f for f in derive_treaty_percentages(ds, {"extra_cession": "Cession %"})}
    assert (out["commission_pct"]["status"], out["commission_pct"]["value"]) == ("UNIFORM", "0.25")
    assert out["cession_pct"]["status"] == "UNIFORM" and out["cession_pct"]["value"] == "0.4"
    assert out["cession_pct"]["source_column"] == "Cession %"
    b = out["brokerage_pct"]
    assert b["status"] == "VARIES" and b["value"] == "0.0125"
    assert [d["row_count"] for d in b["distinct"]] == [8, 2] and b["example_rows"] == [10, 11]
    assert out["tax_pct"]["status"] == "NOT_FOUND" and out["order_pct"]["status"] == "NOT_FOUND"


def test_commission_bundling_brokerage_row():
    cfg = MCRConfig()
    bundled = MoneyRow(1, {R.GROSS: D(220000), R.COMMISSION: D(51700), R.BROKERAGE: D(0)})
    t = TreatyRates(commission_pct=D("0.22"), brokerage_pct=D("0.015"), tax_pct=D("0.11"), cession_pct=D("0.45"))
    trap = detect_bundled_commission(bundled, t, cfg)
    assert trap and trap.rule_id == "MCR-D2" and "bundles brokerage" in trap.message
    honest = MoneyRow(2, {R.GROSS: D(220000), R.COMMISSION: D(48400), R.BROKERAGE: D(3300)})
    assert detect_bundled_commission(honest, t, cfg) is None


def test_gross_is_ceded_with_expected_si_rate():
    t = TreatyRates(commission_pct=D("0.22"), cession_pct=D("0.45"), expected_si_rate=D("0.05"))
    ceded = MoneyRow(1, {R.GROSS: D(157500), R.COMMISSION: D(34650)})
    honest = MoneyRow(2, {R.GROSS: D(350000), R.COMMISSION: D(77000)})
    other = MoneyRow(3, {R.GROSS: D(40000), R.COMMISSION: D(8800)})
    si = {1: D(7_000_000), 2: D(7_000_000), 3: D(7_000_000)}
    traps = detect_gross_is_ceded_rows([ceded, honest, other], si, {}, t, MCRConfig())
    assert [x.row_number for x in traps] == [1]


def test_name_case_standardisation():
    from bordereaux.standardization.service import standardize_name_case as f

    assert f("  ELLIS-PATEL  ") == "Ellis-Patel"
    assert f("NEWMAN, PALMER AND WEBSTER") == "Newman, Palmer and Webster"
    assert f("ACME HOLDINGS LLC") == "Acme Holdings LLC"
    assert f("O'BRIEN BROKERS") == "O'Brien Brokers"
    assert f("McDonald  & Sons") == "McDonald & Sons"  # mixed case untouched (whitespace collapsed)
