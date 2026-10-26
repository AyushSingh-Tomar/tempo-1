from __future__ import annotations

import csv
import io

import pytest

from bordereaux.core.exceptions import ValidationError
from bordereaux.reporting.period import PeriodFilter, filter_processed_csv

pytestmark = pytest.mark.unit

ROWS = [
    ("1", "2024-01-15T00:00:00"),  # full date, Q1
    ("2", "2024-03"),  # month only, Q1
    ("3", "2024-04-30"),  # full date, Q2
    ("4", "2024-05"),  # month only, Q2
    ("5", "2024-12"),  # month only, Q4
    ("6", "2023-12-31"),  # previous year
    ("7", ""),  # no date at all
    ("8", "not a date"),
]


def _csv() -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["source_row_number", "booking_date", "gross_premium"])
    for n, d in ROWS:
        w.writerow([n, d, "100"])
    return buf.getvalue().encode()


def _run(flt: PeriodFilter):
    out, stats = filter_processed_csv(_csv(), flt)
    return [r["source_row_number"] for r in csv.DictReader(io.StringIO(out.decode()))], stats


def test_yearly_filter_includes_month_precision_dates():
    kept, stats = _run(PeriodFilter("booking_date", 2024))
    assert kept == ["1", "2", "3", "4", "5"]
    assert (stats.included_partial_dates, stats.excluded_outside_period, stats.excluded_undated) == (3, 1, 2)
    assert stats.total_rows == 8 and stats.included_rows == 5


def test_quarterly_filter_includes_the_month_precision_dates_inside_it():
    assert _run(PeriodFilter("booking_date", 2024, quarter=1))[0] == ["1", "2"]
    assert _run(PeriodFilter("booking_date", 2024, quarter=2))[0] == ["3", "4"]
    assert _run(PeriodFilter("booking_date", 2024, quarter=3))[0] == []
    assert _run(PeriodFilter("booking_date", 2024, quarter=4))[0] == ["5"]


def test_month_filter_and_other_year():
    assert _run(PeriodFilter("booking_date", 2024, month=3))[0] == ["2"]
    assert _run(PeriodFilter("booking_date", 2023))[0] == ["6"]


def test_filtering_keeps_the_columns_and_does_not_touch_the_values():
    out, _ = filter_processed_csv(_csv(), PeriodFilter("booking_date", 2024, quarter=1))
    rows = list(csv.DictReader(io.StringIO(out.decode())))
    assert list(rows[0]) == ["source_row_number", "booking_date", "gross_premium"]
    assert [r["booking_date"] for r in rows] == ["2024-01-15T00:00:00", "2024-03"]


def test_unknown_column_and_all_undated_column_are_errors():
    with pytest.raises(ValidationError):
        filter_processed_csv(_csv(), PeriodFilter("expiry_date", 2024))
    with pytest.raises(ValidationError):
        filter_processed_csv(_csv(), PeriodFilter("gross_premium", 2024))


@pytest.mark.parametrize("kwargs", [{"quarter": 5}, {"quarter": 0}, {"month": 13}, {"quarter": 1, "month": 1}])
def test_invalid_periods_are_rejected(kwargs):
    with pytest.raises(ValidationError):
        PeriodFilter("booking_date", 2024, **kwargs)


def test_label():
    assert PeriodFilter("d", 2024).label == "2024"
    assert PeriodFilter("d", 2024, quarter=3).label == "2024Q3"
    assert PeriodFilter("d", 2024, month=3).label == "2024-03"
