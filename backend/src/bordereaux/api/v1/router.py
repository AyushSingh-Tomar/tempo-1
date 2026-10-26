"""Root ``/api/v1`` router with foundation endpoints only.

- ``GET /api/v1/me``         - current user (lets the frontend verify its dev token)
- ``GET /api/v1/jobs/{id}``  - job status polling (ADR-006)

Feature routers should be added with ``api_router.include_router(...)``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.api.v1.routes.ai import router as ai_router
from bordereaux.api.v1.routes.cleaning import router as cleaning_router
from bordereaux.api.v1.routes.financial_checks import router as financial_checks_router
from bordereaux.api.v1.routes.format_templates import router as format_templates_router
from bordereaux.api.v1.routes.mapping import router as mapping_router
from bordereaux.api.v1.routes.projects import router as projects_router
from bordereaux.api.v1.routes.reconciliation import router as reconciliation_router
from bordereaux.api.v1.routes.reports import router as reports_router
from bordereaux.api.v1.routes.runs import router as runs_router
from bordereaux.api.v1.routes.treaty import router as treaty_router
from bordereaux.auth.deps import get_current_user
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.utils import envelope
from bordereaux.jobs.service import JobService
from bordereaux.models.job import Job

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(treaty_router)
api_router.include_router(runs_router)
api_router.include_router(cleaning_router)
api_router.include_router(mapping_router)
api_router.include_router(ai_router)
api_router.include_router(format_templates_router)
api_router.include_router(financial_checks_router)
api_router.include_router(reports_router)
api_router.include_router(reconciliation_router)


def serialize_job(job: Job) -> dict[str, Any]:
    return {
        "id": str(job.id),
        "type": job.type,
        "status": job.status,
        "project_id": str(job.project_id) if job.project_id else None,
        "progress": job.progress,
        "output": job.output,
        "error": None
        if job.error is None
        else {k: v for k, v in job.error.items() if k != "traceback"},  # never leak tracebacks
        "created_by": str(job.created_by),
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


@api_router.get("/me", tags=["auth"])
async def read_me(request: Request, user: AuthenticatedUser = Depends(get_current_user)) -> dict[str, Any]:
    return envelope(
        {
            "id": str(user.id),
            "external_id": user.external_id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "permissions": sorted(p.value for p in user.permissions),
        },
        request_id=getattr(request.state, "request_id", None),
    )


@api_router.get("/jobs/{job_id}", tags=["jobs"])
async def read_job(
    job_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    job = await JobService(db).get(job_id)
    return envelope(serialize_job(job), request_id=getattr(request.state, "request_id", None))
