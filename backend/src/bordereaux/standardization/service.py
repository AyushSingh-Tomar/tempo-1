"""Transform the cleaned dataset into a canonical row-level dataset per the
finalized ``ApprovedMapping`` set. Type coercion reuses the same safe parsers
as cleaning (never guesses a value's meaning); a value that doesn't coerce is
kept as its original string and logged as an error rather than dropped.
Lineage is preserved via ``_source_row_number`` on every output row.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.cleaning.parsing import (
    format_partial_date,
    parse_partial_iso,
    try_parse_date,
    try_parse_decimal,
    try_parse_partial_date,
)
from bordereaux.cleaning.service import cleaned_dataset_path, get_latest_cleaning_result
from bordereaux.core.exceptions import NotFoundError, StateError
from bordereaux.core.utils import to_jsonable
from bordereaux.models.mapping import ApprovedMapping, MappingSet
from bordereaux.models.run import ProcessingRun
from bordereaux.mapping.target_format import effective_fields
from bordereaux.storage.service import StorageService

_NUMERIC_TYPES = {"INTEGER", "DECIMAL", "PERCENTAGE"}
_DATE_TYPES = {"DATE"}


def standardized_dataset_path(run_id: UUID) -> str:
    return f"runs/{run_id}/standardized/data.json"


_CODE_TYPES = {"COUNTRY_CODE", "CURRENCY_CODE"}
_LOWER_WORDS = {"and", "of", "the", "&"}
_KEEP_UPPER = {"LLC", "LLP", "PLC", "LP", "GMBH", "AG", "SA", "NV", "BV", "UK", "USA"}


def standardize_name_case(text: str) -> str:
    """Whitespace-trim a name and, when it is ALL CAPS, convert to title case
    ("  ELLIS-PATEL  " -> "Ellis-Patel"). Names that already mix case are left
    exactly as written ("McDonald", "O'Brien")."""
    text = " ".join(text.split())
    if not text or text != text.upper() or text == text.lower():
        return text

    def word(w: str, first: bool) -> str:
        bare = w.strip(",.;")
        if bare.upper() in _KEEP_UPPER:
            return w
        if bare.lower() in _LOWER_WORDS and not first:
            return w.lower()
        return "-".join("'".join(p.capitalize() for p in part.split("'")) for part in w.split("-"))

    return " ".join(word(w, i == 0) for i, w in enumerate(text.split(" ")))


def _coerce(value: Any, field_type: str, field_name: str = "") -> tuple[Any, str | None]:
    """Returns ``(coerced_value, error)``. ``error`` is ``None`` on success."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None, None
    if isinstance(value, str):
        if field_type in _CODE_TYPES:
            return value.strip().upper(), None
        if field_name in ("insured_name", "coverholder_name", "producing_broker", "placing_broker"):
            return standardize_name_case(value), None
    if field_type in _NUMERIC_TYPES:
        parsed, ok = try_parse_decimal(value)
        if not ok:
            return value, f"Could not parse '{value}' as a number"
        return str(parsed), None
    if field_type in _DATE_TYPES:
        parsed, ok = try_parse_date(value)
        if ok:
            return parsed.isoformat(), None
        partial = try_parse_partial_date(value)
        if partial is not None:
            return format_partial_date(*partial), None
        return value, f"Could not parse '{value}' as a date"
    return value, None


async def standardize_run(db: AsyncSession, storage: StorageService, run_id: UUID) -> dict[str, Any]:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    if run.mapping_set_id is None:
        raise StateError("Run has no finalized mapping set to standardize against")

    mapping_set = await db.get(MappingSet, run.mapping_set_id)
    if mapping_set is None:
        raise NotFoundError("Mapping set not found", details={"mapping_set_id": str(run.mapping_set_id)})

    approved_rows = (
        await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == mapping_set.id))
    ).scalars().all()
    mapping = {a.source_column: a.target_field for a in approved_rows}

    target_fields = effective_fields(run)
    field_types = {f["name"]: f.get("type", "STRING") for f in target_fields}

    latest = await get_latest_cleaning_result(db, run_id)
    raw = await storage.download(cleaned_dataset_path(run_id, latest.attempt_number))
    cleaned = json.loads(raw)

    output_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    def canonicalize(row: dict[str, Any], collect_errors: bool) -> dict[str, Any]:
        canonical: dict[str, Any] = {"_source_row_number": row["row_number"]}
        date_flags: dict[str, str] = {}
        for source_col, target_field in mapping.items():
            raw_value = row["values"].get(source_col)
            field_type = field_types.get(target_field, "STRING")
            coerced, error = _coerce(raw_value, field_type, target_field)
            canonical[target_field] = coerced
            if field_type in _DATE_TYPES and parse_partial_iso(coerced) is not None:
                date_flags[target_field] = "MONTH"
            if error and collect_errors:
                errors.append(
                    {
                        "row_number": row["row_number"],
                        "source_column": source_col,
                        "target_field": target_field,
                        "error_type": "TYPE_COERCION_FAILED",
                        "message": error,
                        "source_value": raw_value,
                    }
                )
        if date_flags:
            canonical["_date_flags"] = date_flags
        return canonical

    for row in cleaned["rows"]:
        output_rows.append(canonicalize(row, collect_errors=True))

    # Total/subtotal rows are kept apart from the policy rows: they feed the
    # Category F cross-checks and never reach the processed file.
    total_rows = [
        {**canonicalize(row, collect_errors=False), "_kind": row["kind"], "_data_row_range": row.get("data_row_range")}
        for row in cleaned.get("total_rows", [])
        if row.get("kind") != "FOOTER"
    ]

    payload = {"fields": sorted(set(mapping.values())), "rows": output_rows, "total_rows": total_rows}
    await storage.upload(
        standardized_dataset_path(run_id),
        json.dumps(to_jsonable(payload)).encode("utf-8"),
        content_type="application/json",
        overwrite=True,  # derived data: re-finalising a mapping regenerates it
    )

    coverage = (
        Decimal(len({t for t in mapping.values() if t in field_types})) / Decimal(len(target_fields))
        if target_fields
        else Decimal(0)
    )
    return {
        "row_count": len(output_rows),
        "valid_rows": len(output_rows) - len({e["row_number"] for e in errors}),
        "invalid_rows": len({e["row_number"] for e in errors}),
        "coverage": str(coverage.quantize(Decimal("0.0001"))),
        "partial_date_rows": sum(1 for r in output_rows if r.get("_date_flags")),
        "errors": errors,
    }


async def load_standardized_dataset(storage: StorageService, run_id: UUID) -> dict[str, Any]:
    raw = await storage.download(standardized_dataset_path(run_id))
    return json.loads(raw)
