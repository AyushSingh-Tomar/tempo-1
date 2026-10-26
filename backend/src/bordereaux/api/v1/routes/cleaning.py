"""Step 2-3: clean, review (before/after), acknowledge, rerun."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.cleaning.service import acknowledge_cleaning, list_cleaning_history, rerun_cleaning, run_cleaning
from bordereaux.core.database import get_db
from bordereaux.core.utils import envelope
from bordereaux.models.cleaning import CleaningResult
from bordereaux.storage.service import StorageService

router = APIRouter()


def _get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def serialize_cleaning_result(result: CleaningResult) -> dict[str, Any]:
    return {
        "id": str(result.id),
        "run_id": str(result.run_id),
        "attempt_number": result.attempt_number,
        "before_row_count": result.before_row_count,
        "before_column_count": result.before_column_count,
        "after_row_count": result.after_row_count,
        "after_column_count": result.after_column_count,
        "transformations": result.transformations,
        "warnings": result.warnings,
        "status": result.status,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


class RerunRequest(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/processing-runs/{run_id}/clean", tags=["cleaning"])
async def post_clean(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await run_cleaning(db, _get_storage(request), run_id, user.id)
    return envelope(serialize_cleaning_result(result), request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/cleaning-result", tags=["cleaning"])
async def get_cleaning_result(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    history = await list_cleaning_history(db, run_id)
    data = {
        "latest": serialize_cleaning_result(history[-1]) if history else None,
        "history": [serialize_cleaning_result(h) for h in history],
    }
    return envelope(data, request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/cleaning/acknowledge", tags=["cleaning"])
async def post_acknowledge_cleaning(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from bordereaux.api.v1.routes.runs import serialize_run

    run = await acknowledge_cleaning(db, _get_storage(request), run_id, user.id)
    return envelope(serialize_run(run), request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/cleaning/rerun", tags=["cleaning"])
async def post_rerun_cleaning(
    run_id: UUID,
    payload: RerunRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await rerun_cleaning(db, _get_storage(request), run_id, user.id, payload.reason)
    return envelope(serialize_cleaning_result(result), request_id=getattr(request.state, "request_id", None))
