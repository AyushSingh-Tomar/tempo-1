"""Year / quarter / month filter over the processed file.

A date cell covers a span of months: a full date is one month, a month-and-year
value (``2024-03``, flagged at cleaning) is also one month. A row is kept when
the cell's whole span lies inside the requested window, so a month-precision date
is included by a quarterly or yearly filter that contains that month, and is never
guessed into a day. Rows with no usable date in the filter column cannot be
placed in any period and are left out (and counted, so that is never silent).
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from typing import Any

from bordereaux.core.exceptions import ValidationError

_FULL_DATE_RE = re.compile(r"(\d{4})-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(?:[T ].*)?")
_PARTIAL_RE = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")


@dataclass(frozen=True)
class PeriodFilter:
    field: str
    year: int
    quarter: int | None = None
    month: int | None = None

    def __post_init__(self) -> None:
        if self.quarter is not None and self.month is not None:
            raise ValidationError("Give either a quarter or a month, not both")
        if self.quarter is not None and not 1 <= self.quarter <= 4:
            raise ValidationError("quarter must be between 1 and 4")
        if self.month is not None and not 1 <= self.month <= 12:
            raise ValidationError("month must be between 1 and 12")

    @property
    def window(self) -> tuple[int, int]:
        """Inclusive (first, last) month index of the period, ``year * 12 + month - 1``."""
        if self.quarter is not None:
            first, last = 3 * self.quarter - 2, 3 * self.quarter
        elif self.month is not None:
            first = last = self.month
        else:
            first, last = 1, 12
        return self.year * 12 + first - 1, self.year * 12 + last - 1

    @property
    def label(self) -> str:
        if self.quarter is not None:
            return f"{self.year}Q{self.quarter}"
        if self.month is not None:
            return f"{self.year}-{self.month:02d}"
        return str(self.year)


@dataclass(frozen=True)
class FilterStats:
    total_rows: int
    included_rows: int
    included_partial_dates: int
    excluded_outside_period: int
    excluded_undated: int


def _span(value: Any) -> tuple[tuple[int, int], bool] | None:
    """((first, last) month index, is_partial) of a processed-file date cell."""
    text = str(value or "").strip()
    if m := _FULL_DATE_RE.fullmatch(text):
        idx = int(m.group(1)) * 12 + int(m.group(2)) - 1
        return (idx, idx), False
    if m := _PARTIAL_RE.fullmatch(text):
        idx = int(m.group(1)) * 12 + int(m.group(2)) - 1
        return (idx, idx), True
    return None


def filter_processed_csv(content: bytes, flt: PeriodFilter) -> tuple[bytes, FilterStats]:
    reader = csv.DictReader(io.StringIO(content.decode("utf-8")))
    header = reader.fieldnames or []
    if flt.field not in header:
        raise ValidationError(
            f"The processed file has no column '{flt.field}' to filter on",
            details={"period_field": flt.field},
        )
    first, last = flt.window
    kept: list[dict[str, str]] = []
    rows = included_partial = outside = undated = 0
    for row in reader:
        rows += 1
        span = _span(row.get(flt.field))
        if span is None:
            undated += 1
            continue
        (lo, hi), partial = span
        if first <= lo and hi <= last:
            kept.append(row)
            included_partial += partial
        else:
            outside += 1
    if rows and undated == rows:
        raise ValidationError(
            f"No row has a date in column '{flt.field}', so no period can be applied",
            details={"period_field": flt.field},
        )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(kept)
    return buf.getvalue().encode("utf-8"), FilterStats(rows, len(kept), included_partial, outside, undated)
