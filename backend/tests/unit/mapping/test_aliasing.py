from __future__ import annotations

import pytest

from bordereaux.mapping.aliasing import build_field_index, exact_match, fuzzy_match, normalize_alias
from bordereaux.schemas.loader import load_schema_definition

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def fields():
    definition = load_schema_definition()
    return build_field_index(definition)


def test_normalize_alias_handles_percent_without_colliding():
    assert normalize_alias("Commission %") == "commission pct"
    assert normalize_alias("Commission") == "commission"
    assert normalize_alias("Commission %") != normalize_alias("Commission")


def test_exact_match_on_canonical_name(fields):
    field = exact_match("Gross Premium", fields)
    assert field is not None and field.name == "gross_premium"


def test_exact_match_commission_vs_commission_pct_distinct(fields):
    assert exact_match("Commission", fields).name == "commission"
    assert exact_match("Commission %", fields).name == "commission_pct"


def test_fuzzy_match_abbreviation_within_threshold(fields):
    result = fuzzy_match("Pol Nmbr", fields, threshold=0.80)
    assert result is not None
    assert result[0].name == "policy_ref"


def test_fuzzy_match_returns_none_below_threshold(fields):
    assert fuzzy_match("Completely Unrelated Header Text", fields, threshold=0.90) is None


@pytest.fixture(scope="module")
def mappable(fields):
    """What mapping actually searches: treaty figures are typed in, never column-mapped."""
    return [f for f in fields if f.category != "TREATY_FIGURES"]


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Pol Nmbr", "policy_ref"),
        ("Grs Prem", "gross_premium"),
        ("Insrd Nm", "insured_name"),
        ("Sum Insd", "sum_insured"),
        ("FX Rt", "fx_rate"),
        ("Brkr", "placing_broker"),  # "broker", not "brokerage": the closer abbreviation wins
        ("Net Prm", "net_premium"),
    ],
)
def test_fuzzy_match_resolves_abbreviated_headers_at_the_default_threshold(mappable, header, expected):
    field, score = fuzzy_match(header, mappable)
    assert field.name == expected and 0.90 <= score < 1.0


@pytest.mark.parametrize("header", ["Amount 1", "Vendor Code", "Priority", "Risk City", "Construction", "Cession %"])
def test_fuzzy_match_does_not_invent_a_meaning(mappable, header):
    assert fuzzy_match(header, mappable) is None


def test_fuzzy_match_refuses_to_pick_between_equally_good_fields(fields):
    # "fx rate" is a term of both the row-level rate and the treaty figure.
    assert fuzzy_match("FX Rt", fields) is None


def test_semantic_synonyms_are_dictionary_terms(fields):
    for header, name in {
        "Risk Insured": "insured_name",
        "Placement Intermediary": "placing_broker",
        "Total Insured Value": "sum_insured",
        "Ceding Fee": "commission",
        "Premium Net of Deductions": "net_premium",
    }.items():
        assert exact_match(header, fields).name == name


def test_exact_match_returns_none_for_unknown_header(fields):
    assert exact_match("Totally Unknown Column", fields) is None
