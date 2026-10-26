"""Step 4-5: generate candidates, review, approve/reject/manual, finalize."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.interactions import list_interactions, serialize_interaction
from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import NotFoundError
from bordereaux.core.utils import envelope
from bordereaux.mapping.service import (
    approve_candidate,
    approve_exact_matches,
    create_manual_mapping,
    finalize_mappings,
    generate_mapping_candidates,
    list_candidates,
    reject_candidate,
    reopen_candidate,
    set_target_format,
)
from bordereaux.models.mapping import ApprovedMapping, MappingCandidate, MappingSet
from bordereaux.models.run import ProcessingRun
from bordereaux.mapping.target_format import (
    describe,
    effective_fields,
    parse_columns_file,
    parse_columns_text,
    parse_terms_file,
)
from bordereaux.storage.service import StorageService

router = APIRouter()


async def _get_run(db: AsyncSession, run_id: UUID) -> ProcessingRun:
    run = await db.get(ProcessingRun, run_id)
    if run is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    return run


async def _sample_values(db: AsyncSession, storage: StorageService, run_id: UUID) -> dict[str, list[Any]]:
    """First few non-blank values per source column, from the latest cleaned dataset."""
    import json

    from bordereaux.cleaning.service import cleaned_dataset_path, get_latest_cleaning_result

    try:
        latest = await get_latest_cleaning_result(db, run_id)
        dataset = json.loads(await storage.download(cleaned_dataset_path(run_id, latest.attempt_number)))
    except NotFoundError:
        return {}
    out: dict[str, list[Any]] = {c: [] for c in dataset["columns"]}
    for row in dataset["rows"]:
        for col, bucket in out.items():
            v = row["values"].get(col)
            if len(bucket) < 3 and v not in (None, ""):
                bucket.append(v)
    return out


def _get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def serialize_candidate(c: MappingCandidate, sample_values: list[Any] | None = None) -> dict[str, Any]:
    return {
        "rejection_reason": c.review_comment if c.status == "REJECTED" else None,
        "sample_values": sample_values or [],
        "id": str(c.id),
        "mapping_set_id": str(c.mapping_set_id),
        "source_column": c.source_column,
        "target_field": c.target_field,
        "confidence_total": str(c.confidence_total),
        "confidence_breakdown": c.confidence_breakdown,
        "evidence": c.evidence,
        "status": c.status,
        "auto_approve_eligible": c.auto_approve_eligible,
        "reviewed_by": str(c.reviewed_by) if c.reviewed_by else None,
        "review_comment": c.review_comment,
    }


def serialize_approved(a: ApprovedMapping) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "mapping_set_id": str(a.mapping_set_id),
        "source_column": a.source_column,
        "target_field": a.target_field,
        "origin": a.origin,
        "confidence_total": str(a.confidence_total),
    }


def serialize_mapping_set(m: MappingSet) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "version_id": str(m.version_id),
        "schema_id": m.schema_id,
        "status": m.status,
        "finalized_by": str(m.finalized_by) if m.finalized_by else None,
        "finalized_at": m.finalized_at.isoformat() if m.finalized_at else None,
    }


class ManualMappingRequest(BaseModel):
    source_column: str = Field(..., min_length=1)
    target_field: str = Field(..., min_length=1)


class TargetFormatRequest(BaseModel):
    mode: str = Field(..., pattern="^(DEFAULT|CUSTOM)$")
    columns: list[str] | None = None
    columns_text: str | None = Field(default=None, description="Alternative to ``columns``: newline/comma separated names")
    terms: dict[str, list[str]] | None = Field(
        default=None,
        description="CUSTOM only: recognised terms per final column, e.g. {\"Gross Premium\": [\"GWP\", \"Prime Brute\"]}",
    )
    template_id: UUID | None = Field(
        default=None,
        description="CUSTOM only: use a saved format from the directory instead of ``columns`` / ``terms``",
    )


class RejectRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/processing-runs/{run_id}/mappings/generate", tags=["mapping"])
async def post_generate_mappings(
    run_id: UUID,
    request: Request,
    use_ai: bool = Query(True, description="Set false to skip the AI step and map deterministically only"),
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    mapping_set = await generate_mapping_candidates(db, _get_storage(request), run_id, user.id, use_ai=use_ai)
    ai = await list_interactions(db, run_id, "MAPPING", 1)
    data = {**serialize_mapping_set(mapping_set), "ai": serialize_interaction(ai[0]) if ai else None}
    return envelope(data, request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/mappings/target-format", tags=["mapping"])
async def get_target_format(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    run = await _get_run(db, run_id)
    return envelope(describe(run), request_id=getattr(request.state, "request_id", None))


@router.put("/processing-runs/{run_id}/mappings/target-format", tags=["mapping"])
async def put_target_format(
    run_id: UUID,
    payload: TargetFormatRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    columns = payload.columns or (parse_columns_text(payload.columns_text) if payload.columns_text else None)
    run = await set_target_format(db, run_id, user.id, payload.mode, columns, payload.terms, payload.template_id)
    return envelope(describe(run), request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/mappings/target-format/parse", tags=["mapping"])
async def post_parse_target_format_file(
    run_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    _user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read the column names out of an uploaded CSV/XLSX/TXT (header row). Nothing is saved."""
    await _get_run(db, run_id)
    content = await file.read()
    columns = parse_columns_file(file.filename or "", content)
    return envelope({"columns": columns}, request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/mappings/target-format/parse-terms", tags=["mapping"])
async def post_parse_terms_file(
    run_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    _user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Read a CSV/TSV/XLSX whose header row lists the final columns and whose cells below each
    header are that column's recognised terms. Nothing is saved: the result fills the form."""
    await _get_run(db, run_id)
    content = await file.read()
    return envelope(parse_terms_file(file.filename or "", content), request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/mappings/candidates", tags=["mapping"])
async def get_mapping_candidates(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    candidates = await list_candidates(db, run_id)
    run = await db.get(ProcessingRun, run_id)
    mapping_set = None
    if run is not None and run.mapping_set_id is not None:
        mapping_set = await db.get(MappingSet, run.mapping_set_id)
    if mapping_set is None and run is not None:
        mapping_set = (
            await db.execute(
                select(MappingSet)
                .where(MappingSet.version_id == run.source_version_id)
                .order_by(MappingSet.created_at.desc())
            )
        ).scalars().first()

    approved_rows = []
    if mapping_set is not None:
        approved_rows = (
            await db.execute(select(ApprovedMapping).where(ApprovedMapping.mapping_set_id == mapping_set.id))
        ).scalars().all()

    samples = await _sample_values(db, _get_storage(request), run_id)
    data = {
        "candidates": [serialize_candidate(c, samples.get(c.source_column)) for c in candidates],
        "approved_mappings": [
            {"source_column": a.source_column, "target_field": a.target_field} for a in approved_rows
        ],
        "passthrough_count": sum(1 for c in candidates if c.target_field.startswith("extra_")),
        "required_fields": [f["name"] for f in effective_fields(run) if f.get("required") == "mandatory"]
        if run is not None
        else [],
        "target_format": describe(run) if run is not None else None,
        "mapping_status": mapping_set.status if mapping_set is not None else None,
    }
    return envelope(data, request_id=getattr(request.state, "request_id", None))


@router.post("/mappings/{candidate_id}/approve", tags=["mapping"])
async def post_approve_mapping(
    candidate_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    approved = await approve_candidate(db, candidate_id, user.id)
    return envelope(serialize_approved(approved), request_id=getattr(request.state, "request_id", None))


@router.post("/mappings/{candidate_id}/reject", tags=["mapping"])
async def post_reject_mapping(
    candidate_id: UUID,
    payload: RejectRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_REJECT)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    candidate = await reject_candidate(db, candidate_id, user.id, payload.reason)
    return envelope(serialize_candidate(candidate), request_id=getattr(request.state, "request_id", None))


@router.post("/mappings/{candidate_id}/reopen", tags=["mapping"])
async def post_reopen_mapping(
    candidate_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_REJECT)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    candidate = await reopen_candidate(db, candidate_id, user.id)
    return envelope(serialize_candidate(candidate), request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/mappings/approve-exact", tags=["mapping"])
async def post_approve_exact(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Approve every open candidate that is a 100% data-dictionary match."""
    result = await approve_exact_matches(db, run_id, user.id)
    return envelope(result, request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/mappings/manual", tags=["mapping"])
async def post_manual_mapping(
    run_id: UUID,
    payload: ManualMappingRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_MANUAL)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    approved = await create_manual_mapping(db, run_id, payload.source_column, payload.target_field, user.id)
    return envelope(serialize_approved(approved), request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/mappings/finalize", tags=["mapping"])
async def post_finalize_mappings(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_APPROVE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    mapping_set = await finalize_mappings(db, _get_storage(request), run_id, user.id)
    return envelope(serialize_mapping_set(mapping_set), request_id=getattr(request.state, "request_id", None))
