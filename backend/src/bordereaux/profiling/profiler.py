"""Column-level statistical profiling (MODULE_CONTRACTS.md §4, adapted).

Pure, deterministic Python - no AI, no sampling randomness. Re-profiling the
same ``source_versions`` row (e.g. after a cleaning rerun) replaces the prior
``DataProfile``/``ColumnProfile`` rows in place rather than erroring on the
``version_id`` uniqueness constraint, since only the latest cleaned data is
useful as mapping evidence.
"""

from __future__ import annotations

import statistics
from collections import Counter
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.cleaning.parsing import looks_partial_date, try_parse_date, try_parse_decimal
from bordereaux.core.models import DataType
from bordereaux.models.profile import ColumnProfile, DataProfile

_TYPE_THRESHOLD = Decimal("0.7")
_PERCENTILES = (25, 50, 75, 90, 95, 99)


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _percentile(sorted_values: list[Decimal], pct: int) -> Decimal:
    if not sorted_values:
        return Decimal(0)
    k = (Decimal(pct) / Decimal(100)) * (len(sorted_values) - 1)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    frac = k - f
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * frac


def _infer_type(non_blank: list[Any]) -> DataType:
    if not non_blank:
        return DataType.UNKNOWN
    n = len(non_blank)
    numeric_hits = sum(1 for v in non_blank if try_parse_decimal(v)[1])
    date_hits = sum(1 for v in non_blank if try_parse_date(v)[1] or looks_partial_date(v))
    if Decimal(numeric_hits) / Decimal(n) >= _TYPE_THRESHOLD and numeric_hits >= date_hits:
        decimals = [try_parse_decimal(v)[0] for v in non_blank if try_parse_decimal(v)[1]]
        if all(d == d.to_integral_value() for d in decimals):
            return DataType.INTEGER
        return DataType.DECIMAL
    if Decimal(date_hits) / Decimal(n) >= _TYPE_THRESHOLD:
        return DataType.DATE
    return DataType.STRING


def profile_column(name: str, position: int, values: list[Any]) -> ColumnProfile:
    non_blank = [v for v in values if not _is_blank(v)]
    null_count = len(values) - len(non_blank)
    null_rate = Decimal(null_count) / Decimal(len(values)) if values else Decimal(0)

    data_type = _infer_type(non_blank)
    string_keys = [str(v) for v in non_blank]
    distinct_count = len(set(string_keys))
    distinct_rate = Decimal(distinct_count) / Decimal(len(non_blank)) if non_blank else Decimal(0)
    counts = Counter(string_keys)
    top_values = [{"value": v, "count": c} for v, c in counts.most_common(10)]

    numeric_stats = None
    string_stats = None
    date_stats = None

    if data_type in (DataType.INTEGER, DataType.DECIMAL):
        decimals = sorted(d for v in non_blank if (d := try_parse_decimal(v)[0]) is not None)
        if decimals:
            floats = [float(d) for d in decimals]
            numeric_stats = {
                "min": str(decimals[0]),
                "max": str(decimals[-1]),
                "mean": str(Decimal(str(statistics.fmean(floats)))),
                "median": str(decimals[len(decimals) // 2]),
                "std_dev": str(Decimal(str(statistics.pstdev(floats)))) if len(decimals) > 1 else "0",
                "percentiles": {str(p): str(_percentile(decimals, p)) for p in _PERCENTILES},
            }
    elif data_type is DataType.DATE:
        dates = sorted(d for v in non_blank if (d := try_parse_date(v)[0]) is not None)
        if dates:
            date_stats = {"min_date": dates[0].isoformat(), "max_date": dates[-1].isoformat(), "date_format_patterns": []}
    else:
        if non_blank:
            lengths = [len(str(v)) for v in non_blank]
            string_stats = {
                "min_length": min(lengths),
                "max_length": max(lengths),
                "avg_length": sum(lengths) / len(lengths),
                "empty_count": sum(1 for v in values if isinstance(v, str) and v == ""),
                "patterns": [],
            }

    return ColumnProfile(
        name=name,
        position=position,
        data_type=data_type.value,
        null_count=null_count,
        null_percentage=null_rate.quantize(Decimal("0.0001")),
        distinct_count=distinct_count,
        distinct_percentage=distinct_rate.quantize(Decimal("0.0001")),
        top_values=top_values,
        numeric_stats=numeric_stats,
        string_stats=string_stats,
        date_stats=date_stats,
        patterns=[],
    )


async def profile_dataset(
    db: AsyncSession, version_id: UUID, columns: list[str], rows: list[dict[str, Any]]
) -> DataProfile:
    """Builds column profiles from ``rows`` (shape:
    ``[{"row_number": int, "values": {col: value}}, ...]``) and
    upserts the ``DataProfile``/``ColumnProfile`` rows for ``version_id``."""
    existing = (
        await db.execute(select(DataProfile).where(DataProfile.version_id == version_id))
    ).scalar_one_or_none()

    if existing is not None:
        await db.execute(delete(ColumnProfile).where(ColumnProfile.profile_id == existing.id))
        profile = existing
    else:
        profile = DataProfile(version_id=version_id, row_count=0, column_count=0)
        db.add(profile)
        await db.flush()

    profile.row_count = len(rows)
    profile.column_count = len(columns)
    await db.flush()

    for position, col in enumerate(columns):
        values = [r["values"].get(col) for r in rows]
        column_profile = profile_column(col, position, values)
        column_profile.profile_id = profile.id
        db.add(column_profile)

    await db.flush()
    return profile
