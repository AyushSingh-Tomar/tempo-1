"""Step 11-12: generate reports, download artifacts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import ValidationError
from bordereaux.core.utils import envelope
from bordereaux.models.artifact import PeriodExtractArtifact
from bordereaux.reporting.period import PeriodFilter
from bordereaux.reporting.service import (
    create_period_extract,
    download_period_extract,
    extract_filename,
    generate_reports,
    list_period_extracts,
    resolve_download,
)
from bordereaux.storage.service import StorageService

router = APIRouter()


def _get_storage(request: Request) -> StorageService:
    return request.app.state.storage


@router.post("/processing-runs/{run_id}/reports/generate", tags=["reports"])
async def post_generate_reports(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.REPORT_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    processed, audit = await generate_reports(db, _get_storage(request), run_id, user.id)
    data = {
        "processed_file_artifact": {
            "id": str(processed.id),
            "format": processed.format,
            "checksum": processed.checksum,
            "generated_at": processed.generated_at.isoformat(),
        },
        "audit_report_artifact": {
            "id": str(audit.id),
            "format": audit.format,
            "checksum": audit.checksum,
            "generated_at": audit.generated_at.isoformat(),
        },
    }
    return envelope(data, request_id=getattr(request.state, "request_id", None))


class PeriodExtractRequest(BaseModel):
    period_field: str = Field("booking_date", min_length=1, max_length=100, description="Date column the period applies to")
    year: int = Field(..., ge=1900, le=2200)
    quarter: int | None = Field(None, ge=1, le=4)
    month: int | None = Field(None, ge=1, le=12)


def serialize_extract(e: PeriodExtractArtifact, created: bool | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(e.id),
        "run_id": str(e.run_id),
        "version_number": e.version_number,
        "period_label": e.period_label,
        "period_field": e.period_field,
        "period_year": e.period_year,
        "period_quarter": e.period_quarter,
        "period_month": e.period_month,
        "format": e.format,
        "checksum": e.checksum,
        "source_artifact_id": str(e.source_artifact_id),
        "source_checksum": e.source_checksum,
        "total_rows": e.total_rows,
        "included_rows": e.included_rows,
        "included_partial_dates": e.included_partial_dates,
        "excluded_outside_period": e.excluded_outside_period,
        "excluded_undated": e.excluded_undated,
        "generated_by": str(e.generated_by) if e.generated_by else None,
        "generated_at": e.generated_at.isoformat() if e.generated_at else None,
    }
    if created is not None:
        data["created"] = created  # False: an unchanged result, so the existing latest version is returned
    return data


@router.post("/processing-runs/{run_id}/reports/period-extracts", tags=["reports"])
async def post_period_extract(
    run_id: UUID,
    payload: PeriodExtractRequest,
    request: Request,
    response: Response,
    user: AuthenticatedUser = Depends(require_permission(Permission.REPORT_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Cut the processed file to one year / quarter / month and store it as a new immutable
    version. Dates given only as month and year are included when their month falls in the period."""
    flt = PeriodFilter(payload.period_field, payload.year, payload.quarter, payload.month)
    extract, created = await create_period_extract(db, _get_storage(request), run_id, flt, user.id)
    response.status_code = 201 if created else 200
    return envelope(serialize_extract(extract, created), request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/reports/period-extracts", tags=["reports"])
async def get_period_extracts(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    extracts = await list_period_extracts(db, run_id)
    return envelope({"extracts": [serialize_extract(e) for e in extracts]}, request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/reports/period-extracts/{extract_id}/download", tags=["reports"])
async def download_period_extract_file(
    run_id: UUID,
    extract_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    content, extract = await download_period_extract(db, _get_storage(request), run_id, extract_id, user.id)
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{extract_filename(extract)}"',
            "X-Extract-Version": str(extract.version_number),
            "X-Rows-Total": str(extract.total_rows),
            "X-Rows-Included": str(extract.included_rows),
            "X-Rows-Included-Partial-Dates": str(extract.included_partial_dates),
            "X-Rows-Excluded-Outside-Period": str(extract.excluded_outside_period),
            "X-Rows-Excluded-Undated": str(extract.excluded_undated),
        },
    )


@router.get("/processing-runs/{run_id}/download/{artifact_type}", tags=["reports"])
async def download_artifact(
    run_id: UUID,
    artifact_type: str,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.REPORT_EXPORT)),
    db: AsyncSession = Depends(get_db),
) -> Response:
    if {"year", "quarter", "month", "period_field"} & set(request.query_params):
        raise ValidationError(
            "Period filtering is done through POST /processing-runs/{run_id}/reports/period-extracts",
        )
    content, filename, content_type = await resolve_download(db, _get_storage(request), run_id, artifact_type)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
