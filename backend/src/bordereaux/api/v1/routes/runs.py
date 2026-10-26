"""Steps 1-2: upload, validate, and run detail."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import NotFoundError
from bordereaux.core.utils import envelope
from bordereaux.ingestion.service import create_processing_run_with_upload, validate_processing_run
from bordereaux.models.asset import SourceAsset, SourceVersion
from bordereaux.models.run import ProcessingRun
from bordereaux.storage.service import StorageService

router = APIRouter()


def _get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def serialize_run(run: ProcessingRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "project_id": str(run.project_id),
        "status": run.status,
        "source_asset_id": str(run.source_asset_id) if run.source_asset_id else None,
        "source_version_id": str(run.source_version_id) if run.source_version_id else None,
        "mapping_set_id": str(run.mapping_set_id) if run.mapping_set_id else None,
        "treaty_figures_id": str(run.treaty_figures_id) if run.treaty_figures_id else None,
        "created_by": str(run.created_by),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
    }


def serialize_asset(asset: SourceAsset) -> dict[str, Any]:
    return {
        "id": str(asset.id),
        "name": asset.name,
        "original_filename": asset.original_filename,
        "size_bytes": asset.size_bytes,
        "checksum": asset.checksum,
        "format": asset.format,
        "status": asset.status,
    }


def serialize_version(version: SourceVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "asset_id": str(version.asset_id),
        "version_number": version.version_number,
        "row_count": version.row_count,
        "column_count": version.column_count,
        "status": version.status,
        "structure": version.structure,
    }


@router.post("/projects/{project_id}/processing-runs", tags=["runs"], status_code=201)
async def upload_processing_run(
    project_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    sheet_name: str | None = Form(None),
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = request.app.state.settings
    content = await file.read()
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds the maximum allowed size")

    result = await create_processing_run_with_upload(
        db, _get_storage(request), project_id, file.filename or "upload", content, user.id, sheet_name=sheet_name
    )
    data = {
        "run": serialize_run(result["run"]),
        "asset": serialize_asset(result["asset"]),
        "requires_sheet_selection": result["sheets"] is not None,
        "available_sheets": result["sheets"],
    }
    return envelope(data, request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}", tags=["runs"])
async def get_processing_run(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    return envelope(serialize_run(run), request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/validate", tags=["runs"])
async def validate_run(
    run_id: UUID,
    request: Request,
    sheet_name: str | None = None,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    body: dict[str, Any] = {}
    try:
        body = await request.json()
    except Exception:
        body = {}
    chosen_sheet = sheet_name or (body.get("sheet_name") if isinstance(body, dict) else None)

    version = await validate_processing_run(db, _get_storage(request), run_id, user.id, sheet_name=chosen_sheet)
    return envelope(serialize_version(version), request_id=getattr(request.state, "request_id", None))
