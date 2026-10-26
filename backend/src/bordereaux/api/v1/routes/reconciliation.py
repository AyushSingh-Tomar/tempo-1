"""Reconciliation workspace API: build a final bordereaux / subledger from many
files, then reconcile them with user-defined rules.

    POST /projects/{id}/recon/datasets                 create a draft (BORDEREAUX | SUBLEDGER)
    POST /recon/datasets/{id}/files                    upload one or more files (xlsx / csv / sas7bdat)
    PATCH /recon/datasets/{id}/files/{fid}             choose encoding / sheets / header row
    POST /recon/datasets/{id}/schema-summary           common / unique / partial columns + types
    POST /recon/datasets/{id}/finalize                 combine + standardise -> final dataset + report
    POST /projects/{id}/recon/runs                     run rules (grain, filters, tolerance)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import ValidationError
from bordereaux.core.utils import envelope
from bordereaux.models.recon import ReconDataset, ReconFile, ReconRun
from bordereaux.reconciliation import service as svc
from bordereaux.storage.service import StorageService

router = APIRouter(tags=["reconciliation"])
CREATE = Permission.RECONCILIATION_CREATE
READ = Permission.RECONCILIATION_READ


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _storage(request: Request) -> StorageService:
    return request.app.state.storage


def serialize_file(f: ReconFile) -> dict[str, Any]:
    return {
        "id": str(f.id), "filename": f.filename, "format": f.format, "size_bytes": f.size_bytes, "checksum": f.checksum,
        "encoding": f.encoding, "encoding_info": f.encoding_info, "encoding_choice": f.encoding_choice,
        "sheets": f.sheets, "selected_sheets": f.selected_sheets, "header_row": f.header_row,
        "needs_sheet_choice": len(f.sheets) > 1 and not f.selected_sheets,
    }


def serialize_dataset(ds: ReconDataset, files: list[ReconFile] | None = None, with_report: bool = True) -> dict[str, Any]:
    out = {
        "id": str(ds.id), "project_id": str(ds.project_id), "kind": ds.kind, "name": ds.name, "status": ds.status,
        "row_count": ds.row_count, "column_count": ds.column_count, "config": ds.config,
        "finalized_at": ds.finalized_at.isoformat() if ds.finalized_at else None,
        "created_at": ds.created_at.isoformat() if ds.created_at else None,
    }
    if with_report:
        out["report"] = ds.report
    if files is not None:
        out["files"] = [serialize_file(f) for f in files]
    return out


def serialize_run(run: ReconRun) -> dict[str, Any]:
    return {
        "id": str(run.id), "project_id": str(run.project_id), "name": run.name, "status": run.status,
        "bordereaux_dataset_id": str(run.bordereaux_dataset_id), "subledger_dataset_id": str(run.subledger_dataset_id),
        "config": run.config, "summary": run.summary,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


class CreateDataset(BaseModel):
    kind: str
    name: str = Field(..., min_length=1, max_length=255)


class FilePatch(BaseModel):
    encoding: str | None = Field(None, description="Force an encoding; empty string clears the choice")
    candidate_encodings: list[str] | None = Field(None, description="Restrict auto-detection to these encodings")
    selected_sheets: list[str] | None = None
    header_row: int | None = Field(None, ge=1)


class SchemaRequest(BaseModel):
    column_aliases: dict[str, str] = Field(default_factory=dict, description="column -> column it should be merged into")


class FinalizeRequest(SchemaRequest):
    period_column: str | None = None
    day_first: bool = True
    drop_cross_file_duplicates: bool = False


class EncodingCheck(BaseModel):
    candidate_encodings: list[str] | None = None


class RunRequest(BaseModel):
    name: str | None = None
    bordereaux_dataset_id: UUID
    subledger_dataset_id: UUID
    rules: list[dict[str, Any]]
    group_by: list[dict[str, Any]] = Field(default_factory=list)
    filters: list[dict[str, Any]] = Field(default_factory=list)
    tolerance: dict[str, Any] | None = None


@router.get("/recon/encodings")
async def get_encoding_options(
    request: Request, _u: AuthenticatedUser = Depends(require_permission(READ))
) -> dict[str, Any]:
    return envelope({"encodings": svc.encoding_options(), "defaults": ["utf-8", "cp1252", "latin-1"]}, request_id=_rid(request))


@router.post("/projects/{project_id}/recon/datasets", status_code=201)
async def create_dataset(
    project_id: UUID, payload: CreateDataset, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.create_dataset(db, project_id, payload.kind, payload.name, user.id)
    return envelope(serialize_dataset(ds, []), request_id=_rid(request))


@router.get("/projects/{project_id}/recon/datasets")
async def list_datasets(
    project_id: UUID, request: Request, kind: str | None = Query(None),
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    items = await svc.list_datasets(db, project_id, kind)
    return envelope({"datasets": [serialize_dataset(d, with_report=False) for d in items]}, request_id=_rid(request))


@router.get("/recon/datasets/{dataset_id}")
async def get_dataset(
    dataset_id: UUID, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    return envelope(serialize_dataset(ds, await svc.list_files(db, ds.id)), request_id=_rid(request))


@router.post("/recon/datasets/{dataset_id}/files", status_code=201)
async def upload_files(
    dataset_id: UUID, request: Request,
    files: list[UploadFile] = File(...),
    encoding: str | None = Form(None),
    candidate_encodings: str | None = Form(None, description="comma-separated"),
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    uploads = [(f.filename or "upload", await f.read()) for f in files]
    choice: dict[str, Any] = {}
    if encoding:
        choice["forced"] = encoding
    if candidate_encodings:
        choice["candidates"] = [c.strip() for c in candidate_encodings.split(",") if c.strip()]
    added = await svc.add_files(db, _storage(request), ds, uploads, user.id, request.app.state.settings.max_upload_bytes, choice)
    return envelope({"files": [serialize_file(f) for f in added]}, request_id=_rid(request))


@router.patch("/recon/datasets/{dataset_id}/files/{file_id}")
async def patch_file(
    dataset_id: UUID, file_id: UUID, payload: FilePatch, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    f = await svc.get_file(db, ds, file_id)
    changes = payload.model_dump(exclude_unset=True)
    f = await svc.update_file(db, _storage(request), ds, f, changes, user.id)
    return envelope(serialize_file(f), request_id=_rid(request))


@router.post("/recon/datasets/{dataset_id}/files/{file_id}/encoding-check")
async def check_encoding(
    dataset_id: UUID, file_id: UUID, payload: EncodingCheck, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    f = await svc.get_file(db, ds, file_id)
    return envelope(await svc.encoding_check(_storage(request), f, payload.candidate_encodings), request_id=_rid(request))


@router.delete("/recon/datasets/{dataset_id}/files/{file_id}")
async def delete_file(
    dataset_id: UUID, file_id: UUID, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    await svc.remove_file(db, _storage(request), ds, await svc.get_file(db, ds, file_id), user.id)
    return envelope({"deleted": True}, request_id=_rid(request))


@router.post("/recon/datasets/{dataset_id}/schema-summary")
async def schema_summary(
    dataset_id: UUID, payload: SchemaRequest, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    return envelope(await svc.schema_preview(db, _storage(request), ds, payload.column_aliases), request_id=_rid(request))


@router.post("/recon/datasets/{dataset_id}/finalize")
async def finalize(
    dataset_id: UUID, payload: FinalizeRequest, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    ds = await svc.finalize_dataset(db, _storage(request), ds, payload.model_dump(), user.id)
    return envelope(serialize_dataset(ds, await svc.list_files(db, ds.id)), request_id=_rid(request))


@router.get("/recon/datasets/{dataset_id}/preview")
async def preview(
    dataset_id: UUID, request: Request, limit: int = Query(25, ge=1, le=200),
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    return envelope(await svc.dataset_preview(_storage(request), ds, limit), request_id=_rid(request))


@router.get("/recon/datasets/{dataset_id}/columns/{column}/values")
async def column_values(
    dataset_id: UUID, column: str, request: Request, q: str | None = Query(None), limit: int = Query(50, ge=1, le=500),
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    ds = await svc.get_dataset(db, dataset_id)
    return envelope(await svc.column_values(_storage(request), ds, column, q, limit), request_id=_rid(request))


@router.post("/projects/{project_id}/recon/runs", status_code=201)
async def create_run(
    project_id: UUID, payload: RunRequest, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await svc.run_reconciliation(db, _storage(request), project_id, payload.model_dump(mode="json"), user.id)
    return envelope(serialize_run(run), request_id=_rid(request))


@router.get("/projects/{project_id}/recon/runs")
async def list_runs(
    project_id: UUID, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return envelope({"runs": [serialize_run(r) for r in await svc.list_runs(db, project_id)]}, request_id=_rid(request))


@router.get("/recon/runs/{run_id}")
async def get_run(
    run_id: UUID, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await svc.get_run(db, run_id)
    return envelope({**serialize_run(run), "result": await svc.run_result(_storage(request), run)}, request_id=_rid(request))


@router.get("/recon/runs/{run_id}/records")
async def run_records(
    run_id: UUID, request: Request, rule_id: str = Query(...), side: str = Query(...),
    key: list[str] = Query(default_factory=list),
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await svc.get_run(db, run_id)
    return envelope(await svc.group_records(db, _storage(request), run, rule_id, key, side), request_id=_rid(request))


@router.get("/recon/runs/{run_id}/export")
async def export_run(
    run_id: UUID, request: Request,
    _u: AuthenticatedUser = Depends(require_permission(READ)), db: AsyncSession = Depends(get_db),
) -> Response:
    run = await svc.get_run(db, run_id)
    return Response(
        content=await svc.export_csv(_storage(request), run), media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="reconciliation_{run_id}.csv"'},
    )


@router.post("/processing-runs/{run_id}/reconciliation/bordereaux")
async def reconcile_from_run(
    run_id: UUID, request: Request,
    user: AuthenticatedUser = Depends(require_permission(CREATE)), db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Use a completed run's processed file as the final bordereaux for reconciliation
    (idempotent: one dataset per run). The user then adds a subledger on the reconciliation page."""
    ds, created = await svc.bordereaux_from_run(
        db, _storage(request), run_id, user.id, request.app.state.settings.max_upload_bytes
    )
    return envelope({**serialize_dataset(ds, await svc.list_files(db, ds.id)), "created": created}, request_id=_rid(request))
