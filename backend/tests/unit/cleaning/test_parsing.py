from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from bordereaux.cleaning.parsing import (
    detect_number_locale,
    format_partial_date,
    is_ambiguous_number,
    parse_partial_iso,
    try_parse_date,
    try_parse_decimal,
    try_parse_partial_date,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,234.50", "1234.50"),  # US grouping
        ("12,345,678", "12345678"),
        ("1,234", "1234"),  # a clean thousands group is read as thousands
        ("1.234,56", "1234.56"),  # European grouping
        ("1.234.567", "1234567"),
        ("391707,0", "391707.0"),  # decimal comma: not 3,917,070
        ("12,5", "12.5"),
        ("0,5", "0.5"),
        ("\u20ac 330,034.00", "330034.00"),
        ("\u00a31.234,5", "1234.5"),
        ("(38,320.50)", "-38320.50"),  # accounting negative
        ("-1,234.5", "-1234.5"),
        ("12,5%", "0.125"),
    ],
)
def test_parses_locale_formatted_numbers(text, expected):
    assert try_parse_decimal(text) == (Decimal(expected), True)


@pytest.mark.parametrize("text", ["1,2,3", "1,234,5", "12.34.5", "abc", "1.2,3.4", "N/A"])
def test_never_guesses_at_ambiguous_separators(text):
    assert try_parse_decimal(text) == (None, False)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("27/09/2024", date(2024, 9, 27)),
        ("7-Jul-24", date(2024, 7, 7)),
        ("19-Aug-2024", date(2024, 8, 19)),
        ("7 Jul 24", date(2024, 7, 7)),
        ("11-March-2024", date(2024, 3, 11)),
        ("2024-03-20T00:00:00", date(2024, 3, 20)),  # an Excel date cell after ingestion
        ("2024-03-20 00:00:00", date(2024, 3, 20)),
    ],
)
def test_parses_date_formats(text, expected):
    assert try_parse_date(text) == (expected, True)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Mar-2024", (2024, 3)),
        ("March 2024", (2024, 3)),
        ("mar 2024", (2024, 3)),
        ("Sep, 2024", (2024, 9)),
        ("03/2024", (2024, 3)),
        ("3-2024", (2024, 3)),
        ("2024-03", (2024, 3)),
        ("2024/11", (2024, 11)),
    ],
)
def test_parses_month_and_year_without_a_day(text, expected):
    assert try_parse_partial_date(text) == expected


@pytest.mark.parametrize(
    "text",
    ["Mar-24", "2024", "13/2024", "2024-13", "27/09/2024", "2024-03-15", "7-Jul-24", "N/A", "abc", "03.2024", None, 5],
)
def test_partial_date_parser_rejects_everything_that_is_not_month_and_year(text):
    assert try_parse_partial_date(text) is None


def test_partial_iso_round_trip():
    assert format_partial_date(2024, 3) == "2024-03"
    assert parse_partial_iso("2024-03") == (2024, 3)
    assert parse_partial_iso("2024-03-01") is None and parse_partial_iso("2024-13") is None


@pytest.mark.parametrize(
    ("text", "ambiguous"),
    [("1,234", True), ("1.234", True), ("12,345", True), ("\u20ac 1,234", True), ("(1,234)", True),
     ("0,500", False), ("1,234.5", False), ("12,5", False), ("1,234,567", False), ("1.234.567", False), ("1234", False), (1234, False)],
)
def test_only_a_lone_separator_before_three_digits_is_ambiguous(text, ambiguous):
    assert is_ambiguous_number(text) is ambiguous


@pytest.mark.parametrize(
    ("values", "locale"),
    [
        (["391707,0", "12,5", "1,234"], "EU"),  # decimal commas prove the convention
        (["1.234,56", "7,25"], "EU"),
        (["1.234.567", "1.234"], "EU"),
        (["1,234.50", "12.5", "1,234"], "US"),
        (["12,345,678", "1,234"], "US"),
        (["1,234", "5,678"], None),  # nothing proves it
        (["330,034.00", "391707,0"], None),  # one of each: a tie decides nothing
        ([1234, 12.5, None, "N/A"], None),
    ],
)
def test_the_column_convention_comes_from_its_unambiguous_values(values, locale):
    assert detect_number_locale(values) == locale


@pytest.mark.parametrize(
    ("text", "locale", "expected"),
    [
        ("1,234", None, "1234"),  # default: thousands
        ("1,234", "US", "1234"),
        ("1,234", "EU", "1.234"),  # decimal comma in a European column
        ("1.234", None, "1.234"),  # default: decimal dot
        ("1.234", "US", "1.234"),
        ("1.234", "EU", "1234"),  # thousands dot in a European column
        ("12,5", "US", "12.5"),  # unambiguous values ignore the column's convention
        ("1,234.50", "EU", "1234.50"),
        ("1.234,56", "US", "1234.56"),
        ("0,500", None, "0.500"),
        ("\u20ac 1,234", "EU", "1.234"),
        ("(1,234)", "EU", "-1.234"),
    ],
)
def test_ambiguous_separators_follow_the_given_locale(text, locale, expected):
    assert try_parse_decimal(text, locale) == (Decimal(expected), True)
