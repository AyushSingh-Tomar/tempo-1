"""User-declared money relations: validation, description and deterministic evaluation."""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from bordereaux.money_rules import MCRConfig, TreatyRates
from bordereaux.money_rules import relations as rel


def rows(*dicts: dict) -> list[dict]:
    return [{"_source_row_number": i + 1, **d} for i, d in enumerate(dicts)]


def relation(target: str, terms: list[dict]) -> rel.Relation:
    return rel.Relation("r1", "label", target, rel.parse_terms(terms))


NET = [{"field": "gross", "sign": 1}, {"field": "comm", "sign": -1}, {"field": "tax", "sign": -1}]


def test_deduction_holds_and_fails_per_row() -> None:
    data = rows(
        {"gross": "1000", "comm": "250", "tax": "80", "net": "670"},
        {"gross": "1000", "comm": "250", "tax": "80", "net": "700"},  # wrong
    )
    ev = rel.evaluate_relation(relation("net", NET), data, TreatyRates(), MCRConfig())
    assert ev.evaluated == 2
    assert [f.row_number for f in ev.failed] == [2]
    assert ev.failed[0].expected == D("670") and ev.failed[0].observed == D("700")
    assert ev.agreement == D("0.5")


def test_tolerance_absorbs_rounding() -> None:
    data = rows({"gross": "1000", "comm": "250", "tax": "80", "net": "670.5"})  # within 0.5%
    assert not rel.evaluate_relation(relation("net", NET), data, TreatyRates(), MCRConfig()).failed


def test_treaty_ratio_and_literal_factor() -> None:
    data = rows({"gross": "1000", "comm": "250"}, {"gross": "2000", "comm": "400"})
    r = relation("comm", [{"field": "gross", "sign": 1, "factors": ["commission_pct"]}])
    ev = rel.evaluate_relation(r, data, TreatyRates(commission_pct=D("0.25")), MCRConfig())
    assert [f.row_number for f in ev.failed] == [2]
    half = relation("comm", [{"field": "gross", "sign": 1, "factors": ["0.5"]}])
    assert rel.evaluate_relation(half, rows({"gross": "10", "comm": "5"}), TreatyRates(), MCRConfig()).evaluated == 1


def test_missing_treaty_figure_is_skipped_with_reason_not_silently_passed() -> None:
    r = relation("comm", [{"field": "gross", "sign": 1, "factors": ["commission_pct"]}])
    ev = rel.evaluate_relation(r, rows({"gross": "1000", "comm": "999"}), TreatyRates(), MCRConfig())
    assert ev.evaluated == 0 and not ev.failed
    assert "commission_pct" in (ev.skipped_reason or "")


def test_rows_missing_a_value_are_not_evaluated() -> None:
    data = rows({"gross": "1000", "comm": "", "tax": "80", "net": "670"}, {"gross": "1000", "comm": "250", "tax": "80", "net": "670"})
    ev = rel.evaluate_relation(relation("net", NET), data, TreatyRates(), MCRConfig())
    assert ev.evaluated == 1 and not ev.failed


def test_per_row_fx_wins_over_the_treaty_rate() -> None:
    r = relation("settled", [{"field": "share", "sign": 1, "factors": ["fx_rate"]}])
    data = rows({"share": "100", "settled": "85", "ccy": "USD"}, {"share": "100", "settled": "100", "ccy": "EUR"})
    fx = {"USD": D("0.85"), "EUR": D("1")}
    ev = rel.evaluate_relation(r, data, TreatyRates(), MCRConfig(), lambda row: fx.get(row["ccy"]))
    assert ev.evaluated == 2 and not ev.failed


def test_zero_target_against_nonzero_expectation_is_a_failure() -> None:
    ev = rel.evaluate_relation(relation("net", NET), rows({"gross": "1000", "comm": "0", "tax": "0", "net": "0"}), TreatyRates(), MCRConfig())
    assert len(ev.failed) == 1


@pytest.mark.parametrize(
    "terms, message",
    [
        ([], "at least one term"),
        ([{"field": "a", "sign": 2}], r"must be \+1 or -1"),
        ([{"field": "", "sign": 1}], "needs a field"),
        ([{"field": "a", "sign": 1, "factors": ["rm -rf"]}], "not a treaty figure"),
        ([{"field": "a"}] * 9, "at most"),
    ],
)
def test_invalid_definitions_are_rejected(terms: list[dict], message: str) -> None:
    with pytest.raises(rel.RelationError, match=message):
        rel.parse_terms(terms)


def test_validate_checks_columns_and_self_reference() -> None:
    terms = rel.parse_terms(NET)
    with pytest.raises(rel.RelationError, match="not a numeric column"):
        rel.validate("net", terms, {"gross", "comm", "net"})
    with pytest.raises(rel.RelationError, match="itself"):
        rel.validate("gross", rel.parse_terms([{"field": "gross", "sign": 1}]), {"gross"})
    rel.validate("net", terms, {"gross", "comm", "tax", "net"})


def test_describe_signature_and_category() -> None:
    terms = rel.parse_terms(NET)
    assert rel.describe("net", terms) == "net = gross - comm - tax"
    assert rel.describe("net", terms, {"net": "Net Premium"}).startswith("Net Premium = ")
    reordered = rel.parse_terms([NET[2], NET[0], NET[1]])
    assert rel.signature("net", terms) == rel.signature("net", reordered)
    assert rel.category_for(terms) == "CORE_DEDUCTION"
    assert rel.category_for(rel.parse_terms([{"field": "g", "sign": 1, "factors": ["commission_pct"]}])) == "TREATY_RATIO"
    assert rel.category_for(rel.parse_terms([{"field": "g", "sign": 1, "factors": ["order_pct"]}])) == "BASIS_ALIGNMENT"
