from __future__ import annotations

import pytest

from bordereaux.cleaning.rules import clean_dataset

pytestmark = pytest.mark.unit


def _dataset(columns, rows):
    return {"columns": columns, "rows": [{"row_number": i + 1, "values": v} for i, v in enumerate(rows)]}


def test_drops_blank_rows_and_columns():
    data = _dataset(
        ["A", "B", "Blank"],
        [
            {"A": "1", "B": "2", "Blank": None},
            {"A": None, "B": None, "Blank": None},  # fully blank row
            {"A": "3", "B": "4", "Blank": ""},
        ],
    )
    outcome = clean_dataset(data)
    assert outcome.before_row_count == 3
    assert outcome.after_row_count == 2
    assert outcome.before_column_count == 3
    assert outcome.after_column_count == 2
    assert any(t["type"] == "drop_blank_row" for t in outcome.transformations)
    assert any(t["type"] == "drop_blank_column" and "Blank" in t["columns"] for t in outcome.transformations)


def test_flags_duplicate_rows_without_removing_them():
    data = _dataset(["A", "B"], [{"A": "1", "B": "2"}, {"A": "1", "B": "2"}])
    outcome = clean_dataset(data)
    assert outcome.after_row_count == 2  # not removed
    assert any(w["type"] == "duplicate_row" for w in outcome.warnings)


def test_normalizes_null_tokens_and_whitespace():
    data = _dataset(["A", "B"], [{"A": "N/A", "B": "  hello   world  "}])
    outcome = clean_dataset(data)
    row = outcome.rows[0]["values"]
    assert row["A"] is None
    assert row["B"] == "hello world"


def test_normalizes_numeric_formatting_and_warns_on_unparseable():
    data = _dataset(
        ["Amount"],
        [
            {"Amount": "1,000.50"},
            {"Amount": "2,000.00"},
            {"Amount": "3,000.00"},
            {"Amount": "4,000.00"},
            {"Amount": "not-a-number"},
        ],
    )
    outcome = clean_dataset(data)
    values = [r["values"]["Amount"] for r in outcome.rows]
    assert "1000.50" in values
    assert any(w["type"] == "unparseable_numeric" for w in outcome.warnings)


def test_normalizes_column_names_preserving_meaning():
    data = _dataset(["  Pol  No  "], [{"  Pol  No  ": "ABC"}])
    outcome = clean_dataset(data)
    assert outcome.columns == ["Pol No"]
    assert outcome.rows[0]["values"]["Pol No"] == "ABC"


def test_deterministic_output_for_same_input():
    data = _dataset(["A"], [{"A": "1,000"}, {"A": "N/A"}])
    r1 = clean_dataset(data)
    r2 = clean_dataset(data)
    assert r1.rows == r2.rows
    assert r1.transformations == r2.transformations
    assert r1.warnings == r2.warnings


def _policy(n):
    return {"Policy": f"POL-{n}", "Insured": f"Name {n}", "Gross": str(100 * n), "Net": str(80 * n)}


def test_total_subtotal_and_footer_rows_are_set_aside_not_deleted():
    rows = [_policy(i) for i in (1, 2, 3)]
    rows.append({"Policy": "SUBTOTAL", "Insured": "SUBTOTAL (rows 1-3)", "Gross": "600", "Net": "480"})
    rows.append({"Policy": None, "Insured": "Grand Total", "Gross": "1200", "Net": "960"})
    rows.append({"Policy": "--- End of bordereaux ---", "Insured": None, "Gross": None, "Net": None})
    outcome = clean_dataset(_dataset(["Policy", "Insured", "Gross", "Net"], rows))

    assert [r["row_number"] for r in outcome.rows] == [1, 2, 3]
    kinds = {r["row_number"]: (r["kind"], r["data_row_range"]) for r in outcome.total_rows}
    assert kinds == {4: ("SUBTOTAL", [1, 3]), 5: ("GRAND_TOTAL", None), 6: ("FOOTER", None)}
    assert any(t["type"] == "separate_total_row" and t["count"] == 3 for t in outcome.transformations)


@pytest.mark.parametrize("name", ["Total Energies SE", "Totalitarian Ltd", "Subtotal Holdings plc"])
def test_a_policy_whose_name_merely_starts_with_total_is_data(name):
    rows = [_policy(1), {**_policy(2), "Insured": name}]
    outcome = clean_dataset(_dataset(["Policy", "Insured", "Gross", "Net"], rows))
    assert [r["row_number"] for r in outcome.rows] == [1, 2] and outcome.total_rows == []


def test_a_sparse_row_is_only_a_footer_when_it_reads_like_one():
    rows = [_policy(1), {"Policy": "POL-77", "Insured": None, "Gross": None, "Net": None}]
    outcome = clean_dataset(_dataset(["Policy", "Insured", "Gross", "Net"], rows))
    assert [r["row_number"] for r in outcome.rows] == [1, 2] and outcome.total_rows == []


def test_month_and_year_dates_are_kept_at_month_precision_and_flagged():
    rows = [
        {"Policy": "P1", "Booked": "15/01/2024"},
        {"Policy": "P2", "Booked": "Mar-2024"},
        {"Policy": "P3", "Booked": "05/2024"},
        {"Policy": "P4", "Booked": "2024-07-09"},
    ]
    outcome = clean_dataset(_dataset(["Policy", "Booked"], rows))
    assert [r["values"]["Booked"] for r in outcome.rows] == ["2024-01-15", "2024-03", "2024-05", "2024-07-09"]
    flagged = [w for w in outcome.warnings if w["type"] == "partial_date"]
    assert [(w["row_number"], w["value"], w["normalized"], w["precision"]) for w in flagged] == [
        (2, "Mar-2024", "2024-03", "MONTH"),
        (3, "05/2024", "2024-05", "MONTH"),
    ]
    assert {"type": "partial_date_summary", "column": "Booked", "count": 2} == {
        k: v for k, v in next(w for w in outcome.warnings if w["type"] == "partial_date_summary").items() if k != "message"
    }
    assert not any(w["type"] == "unparseable_date" for w in outcome.warnings)
    assert any(t["type"] == "normalize_partial_date" and t["cells_affected"] == 2 for t in outcome.transformations)


def test_a_day_is_never_invented_for_a_month_only_date():
    outcome = clean_dataset(_dataset(["Booked"], [{"Booked": "Mar-2024"}, {"Booked": "Apr-2024"}, {"Booked": "May-2024"}]))
    assert [r["values"]["Booked"] for r in outcome.rows] == ["2024-03", "2024-04", "2024-05"]


def _amounts(*values):
    return clean_dataset(_dataset(["Amount"], [{"Amount": v} for v in values]))


def test_a_decimal_comma_column_reads_1_234_as_one_point_two_three_four():
    outcome = _amounts("391707,0", "12,5", "1,234", "2,000")
    assert [r["values"]["Amount"] for r in outcome.rows] == ["391707.0", "12.5", "1.234", "2.000"]
    assert {"type": "number_locale", "column": "Amount", "locale": "EU", "cells_affected": 2} in outcome.transformations
    assert not any(w["type"] == "ambiguous_number_format" for w in outcome.warnings)


def test_a_thousands_comma_column_keeps_1_234_as_1234():
    outcome = _amounts("1,234.50", "12.5", "1,234", "2,000")
    assert [r["values"]["Amount"] for r in outcome.rows] == ["1234.50", "12.5", "1234", "2000"]
    assert {"type": "number_locale", "column": "Amount", "locale": "US", "cells_affected": 2} in outcome.transformations


def test_an_undecidable_column_defaults_to_thousands_but_is_flagged_for_review():
    outcome = _amounts("1,234", "5,678", "9,100", "250")
    assert [r["values"]["Amount"] for r in outcome.rows] == ["1234", "5678", "9100", "250"]
    flagged = [w for w in outcome.warnings if w["type"] == "ambiguous_number_format"]
    assert len(flagged) == 1 and flagged[0]["count"] == 3 and flagged[0]["examples"] == ["1,234", "5,678", "9,100"]


def test_columns_decide_their_convention_independently():
    data = _dataset(["EU", "US"], [{"EU": "12,5", "US": "12.5"}, {"EU": "1,234", "US": "1,234"}, {"EU": "7,25", "US": "7.25"}])
    rows = clean_dataset(data).rows
    assert [r["values"]["EU"] for r in rows] == ["12.5", "1.234", "7.25"]
    assert [r["values"]["US"] for r in rows] == ["12.5", "1234", "7.25"]
