"""Structure/header detection (StructureDetector contract, adapted).

Real bordereaux files are not guaranteed to have the header on row 1 - some
carry title/metadata rows (cedant name, period, etc.) and blank spacer rows
before the real header. This module locates the header row heuristically:
the first row, among the first ``max_scan`` rows, whose non-empty cell count
is close to the widest row seen (headers are as wide as the data) *and*
whose non-empty cells are mostly label-like strings (not numbers/dates) -
title rows are narrow (1-2 cells), data rows are wide but numeric/mixed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from bordereaux.core.exceptions import IngestionError

MAX_HEADER_SCAN_ROWS = 30


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _row_non_empty_count(row: list[Any]) -> int:
    return sum(1 for v in row if not _is_blank(v))


def _looks_like_label(value: Any) -> bool:
    if _is_blank(value):
        return False
    if isinstance(value, (int, float, Decimal)):
        return False
    if isinstance(value, (datetime, date)):
        return False
    return True


@dataclass(frozen=True)
class StructureDetection:
    header_row: int  # 0-indexed position within the rows list
    data_start_row: int
    data_end_row: int  # inclusive
    column_names: list[str]


def detect_header_row(rows: list[list[Any]], max_scan: int = MAX_HEADER_SCAN_ROWS) -> int:
    if not rows:
        raise IngestionError("File has no rows; cannot detect a header.")
    scan = rows[:max_scan]
    widths = [_row_non_empty_count(r) for r in scan]
    target = max(widths) if widths else 0
    if target == 0:
        raise IngestionError("File has no non-empty cells in its first rows; cannot detect a header.")
    threshold = max(2, int(target * 0.6))
    for i, row in enumerate(scan):
        if widths[i] < threshold:
            continue
        non_blank = [v for v in row if not _is_blank(v)]
        if not non_blank:
            continue
        label_like = sum(1 for v in non_blank if _looks_like_label(v))
        if label_like >= 0.6 * len(non_blank):
            return i
    # Fallback: assume the file simply has no title rows.
    return 0


def build_column_names(header_values: list[Any]) -> list[str]:
    names: list[str] = []
    seen: dict[str, int] = {}
    for idx, value in enumerate(header_values):
        name = str(value).strip() if not _is_blank(value) else f"Column_{idx + 1}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        names.append(name)
    return names


def detect_structure(rows: list[list[Any]]) -> StructureDetection:
    header_idx = detect_header_row(rows)
    header_values = rows[header_idx]
    column_names = build_column_names(header_values)

    data_row_indices = [i for i in range(header_idx + 1, len(rows)) if _row_non_empty_count(rows[i]) > 0]
    if not data_row_indices:
        raise IngestionError("Header row detected but no data rows found beneath it.")

    return StructureDetection(
        header_row=header_idx,
        data_start_row=data_row_indices[0],
        data_end_row=data_row_indices[-1],
        column_names=column_names,
    )
