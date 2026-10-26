"""User-supplied recognised terms for a custom final-column format."""

from __future__ import annotations

import io

import openpyxl
import pytest

from bordereaux.core.exceptions import ValidationError
from bordereaux.mapping.aliasing import build_field_index, exact_match, exact_matches
from bordereaux.mapping.target_format import build_custom_fields, clean_terms, parse_terms_file

pytestmark = pytest.mark.unit


def by_label(fields):
    return {f["display_name"]: f for f in fields}


# --- build_custom_fields ------------------------------------------------------------


def test_without_terms_nothing_changes():
    fields = build_custom_fields(["UMR", "Policy Holder Mood"])
    assert [f["name"] for f in fields] == ["umr", "policy_holder_mood"]
    assert all("user_terms" not in f for f in fields)
    assert by_label(fields)["Policy Holder Mood"]["aliases"] == ["Policy Holder Mood"]


def test_terms_become_recognised_aliases_of_a_new_column():
    f = by_label(build_custom_fields(["Premium Due", "UMR"], {"Premium Due": ["Prime Brute", "  Amount   Charged "]}))["Premium Due"]
    assert f["aliases"] == ["Premium Due", "Prime Brute", "Amount Charged"]
    assert f["user_terms"] == ["Prime Brute", "Amount Charged"]
    index = build_field_index({"fields": [f]})
    assert exact_match("prime brute", index).name == f["name"]
    assert exact_match("AMOUNT CHARGED", index).name == f["name"]


def test_terms_are_added_to_a_dictionary_column_and_keep_its_meaning():
    f = by_label(build_custom_fields(["Gross Premium"], {"Gross Premium": ["Prime Brute"]}))["Gross Premium"]
    assert f["name"] == "gross_premium" and f["money_role"] == "GROSS" and f["dictionary_match"] == "gross_premium"
    assert {"GWP", "Prime Brute", "Gross Premium"} <= set(f["aliases"])  # built-in synonyms stay as a fallback


def test_terms_can_identify_a_dictionary_field_when_the_name_does_not():
    f = by_label(build_custom_fields(["Premium Due"], {"Premium Due": ["GWP", "Prime Brute"]}))["Premium Due"]
    assert f["name"] == "gross_premium" and f["money_role"] == "GROSS" and f["type"] == "DECIMAL"


def test_terms_pointing_at_different_dictionary_fields_do_not_guess():
    f = by_label(build_custom_fields(["Mystery"], {"Mystery": ["GWP", "Commission"]}))["Mystery"]
    assert f["category"] == "CUSTOM" and "money_role" not in f


def test_a_term_the_user_lists_is_taken_off_other_columns_built_in_synonyms():
    # "Premium" is a built-in synonym of Gross Premium; the user says it belongs to Net Amount Due.
    fields = build_custom_fields(["Gross Premium", "Net Amount Due"], {"Net Amount Due": ["Premium"]})
    index = build_field_index({"fields": fields})
    hit = exact_match("Premium", index)
    assert hit.display_name == "Net Amount Due"
    assert len(exact_matches("Premium", index)) == 1
    gross = by_label(fields)["Gross Premium"]
    assert "Premium" not in gross["aliases"] and "Gross Premium" in gross["aliases"] and "GWP" in gross["aliases"]


def test_the_same_term_for_two_columns_stays_ambiguous():
    fields = build_custom_fields(["Alpha", "Beta"], {"Alpha": ["Shared"], "Beta": ["shared"]})
    assert {f.display_name for f in exact_matches("Shared", build_field_index({"fields": fields}))} == {"Alpha", "Beta"}


def test_a_columns_own_label_survives_when_it_is_another_columns_term():
    fields = build_custom_fields(["Alpha", "Beta"], {"Beta": ["Alpha"]})
    assert "Alpha" in by_label(fields)["Alpha"]["aliases"]


def test_the_default_dictionary_is_not_modified_by_custom_terms():
    from bordereaux.mapping.target_format import default_fields

    before = {f["name"]: list(f["aliases"]) for f in default_fields() if "aliases" in f}
    build_custom_fields(["Gross Premium", "Net Amount Due"], {"Gross Premium": ["Prime Brute"], "Net Amount Due": ["Premium"]})
    assert {f["name"]: list(f["aliases"]) for f in default_fields() if "aliases" in f} == before


# --- clean_terms --------------------------------------------------------------------


def test_clean_terms_matches_keys_loosely_and_removes_blanks_and_duplicates():
    out = clean_terms({"gross  PREMIUM": ["GWP", "", "gwp", "  Prime Brute ", None], "UMR": []}, ["Gross Premium", "UMR"])
    assert out == {"Gross Premium": ["GWP", "Prime Brute"]}


def test_clean_terms_rejects_columns_that_are_not_in_the_final_list():
    with pytest.raises(ValidationError) as exc:
        clean_terms({"Gross Premium": ["GWP"], "Typo Column": ["x"]}, ["Gross Premium"])
    assert exc.value.details == [{"unknown_columns": ["Typo Column"]}]


def test_clean_terms_limits():
    with pytest.raises(ValidationError):
        clean_terms({"A": ["x" * 201]}, ["A"])
    with pytest.raises(ValidationError):
        clean_terms({"A": [f"term {i}" for i in range(201)]}, ["A"])
    assert clean_terms(None, ["A"]) == {} and clean_terms({}, ["A"]) == {}


# --- parse_terms_file ---------------------------------------------------------------


def test_csv_headers_are_columns_and_values_below_are_terms():
    csv_bytes = "\ufeffGross Premium,Net Premium,UMR\nGWP,NWP,\nPrime Brute,,\nWritten Premium,,\n".encode("utf-8")
    assert parse_terms_file("terms.csv", csv_bytes) == {
        "columns": ["Gross Premium", "Net Premium", "UMR"],
        "terms": {"Gross Premium": ["GWP", "Prime Brute", "Written Premium"], "Net Premium": ["NWP"]},
        "skipped_terms": 0,
    }


def test_columns_without_any_terms_are_still_columns_and_ragged_rows_are_fine():
    out = parse_terms_file("t.csv", b"A,B,C\nx\n\ny,z\n")
    assert out["columns"] == ["A", "B", "C"] and out["terms"] == {"A": ["x", "y"], "B": ["z"]}


def test_terms_under_an_empty_header_are_skipped_and_counted():
    out = parse_terms_file("t.csv", b"A,,C\nx,orphan1,1\n,orphan2,\n")
    assert out["columns"] == ["A", "C"] and out["terms"] == {"A": ["x"], "C": ["1"]} and out["skipped_terms"] == 2


def test_a_repeated_header_adds_to_the_first_one():
    out = parse_terms_file("t.csv", b"Gross Premium,gross premium\nGWP,Prime Brute\n")
    assert out["columns"] == ["Gross Premium"] and out["terms"] == {"Gross Premium": ["GWP", "Prime Brute"]}


def test_tsv_and_xlsx_are_read_the_same_way():
    assert parse_terms_file("t.tsv", b"A\tB\nx\ty\n")["terms"] == {"A": ["x"], "B": ["y"]}
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Gross Premium", "Count"])
    ws.append(["GWP", 12])
    ws.append([None, 7])
    buf = io.BytesIO()
    wb.save(buf)
    assert parse_terms_file("t.xlsx", buf.getvalue()) == {
        "columns": ["Gross Premium", "Count"],
        "terms": {"Gross Premium": ["GWP"], "Count": ["12", "7"]},
        "skipped_terms": 0,
    }


def test_empty_unsupported_and_oversized_files():
    assert parse_terms_file("t.csv", b"\n\n") == {"columns": [], "terms": {}, "skipped_terms": 0}
    with pytest.raises(ValidationError):
        parse_terms_file("t.txt", b"A\nx")
    with pytest.raises(ValidationError):
        parse_terms_file("t.csv", b"A\n" + b"x\n" * (1024 * 1024 + 1))
