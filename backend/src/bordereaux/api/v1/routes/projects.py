"""Minimal project CRUD - needed as the entry point for the processing-run
workflow (`POST /projects/{project_id}/processing-runs` requires an existing
project), but not owned by any single agent's module boundary in this
iteration, so it lives here rather than under a dedicated ``projects/``
package. Scope is deliberately minimal: create + list + get + soft delete (project owners
only, after typing the project's name) - no update/archive this iteration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from bordereaux.core.models import ActorType, AuditAction, ProjectStatus, UserRole
from bordereaux.core.utils import envelope, model_snapshot, utcnow
from bordereaux.models.project import Project

router = APIRouter()


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(None, max_length=2000)


def serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "created_by": str(project.created_by),
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


@router.post("/projects", tags=["projects"], status_code=201)
async def create_project(
    payload: CreateProjectRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.PROJECT_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = Project(name=payload.name, description=payload.description, created_by=user.id)
    db.add(project)
    await db.flush()
    await AuditService(db).log(
        event_type="project.created",
        target_type="Project",
        target_id=project.id,
        action=AuditAction.CREATE,
        actor_id=user.id,
        actor_type=ActorType.USER,
        after_state=model_snapshot(project),
        project_id=project.id,
    )
    await db.commit()
    return envelope(serialize_project(project), request_id=getattr(request.state, "request_id", None))


@router.get("/projects", tags=["projects"])
async def list_projects(
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.PROJECT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(Project).where(Project.deleted_at.is_(None)).order_by(Project.created_at.desc())
    projects = list((await db.execute(stmt)).scalars().all())
    return envelope(
        [serialize_project(p) for p in projects],
        request_id=getattr(request.state, "request_id", None),
        total=len(projects),
    )


@router.get("/projects/{project_id}", tags=["projects"])
async def get_project(
    project_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.PROJECT_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    project = await db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise NotFoundError("Project not found", details={"project_id": str(project_id)})
    return envelope(serialize_project(project), request_id=getattr(request.state, "request_id", None))


class DeleteProjectRequest(BaseModel):
    confirm_name: str = Field(..., max_length=200, description="The project's exact name, typed to confirm")


@router.delete("/projects/{project_id}", tags=["projects"])
async def delete_project(
    project_id: UUID,
    payload: DeleteProjectRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.PROJECT_DELETE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Remove a project from the directory. Only the ``project_owner`` role may do this (the
    admin role is deliberately not enough), and only after typing the project's exact name.

    It is a soft delete: the project, its runs, uploads, artifacts and audit trail are kept
    (raw files and audit events are immutable); it just stops being listed or usable."""
    if user.role != UserRole.PROJECT_OWNER.value:
        await AuditService(db).log(
            event_type="auth.permission_denied",
            target_type="Project",
            target_id=project_id,
            action=AuditAction.READ,
            actor_id=user.id,
            actor_type=ActorType.USER,
            metadata={"permission": Permission.PROJECT_DELETE.value, "role": user.role, "reason": "project_owner_only"},
        )
        await db.commit()
        raise AuthorizationError("Only a project owner can delete a project")
    project = await db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise NotFoundError("Project not found", details={"project_id": str(project_id)})
    if payload.confirm_name.strip() != project.name.strip():
        raise ValidationError("The name you typed does not match the project name", code="PROJECT_NAME_MISMATCH")
    before = model_snapshot(project)
    project.deleted_at = utcnow()
    project.status = ProjectStatus.DELETED.value
    await db.flush()
    await AuditService(db).log(
        event_type="project.deleted",
        target_type="Project",
        target_id=project.id,
        action=AuditAction.DELETE,
        actor_id=user.id,
        actor_type=ActorType.USER,
        before_state=before,
        after_state={"deleted_at": project.deleted_at.isoformat(), "status": project.status},
        project_id=project.id,
    )
    await db.commit()
    return envelope({"id": str(project.id), "deleted": True}, request_id=getattr(request.state, "request_id", None))
