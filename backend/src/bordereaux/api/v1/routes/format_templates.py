"""Saved final-format templates: the platform-wide directory (list, add, change, remove)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.utils import envelope
from bordereaux.mapping.format_templates import (
    create_template,
    delete_template,
    get_template,
    list_templates,
    serialize_template,
    update_template,
)
from bordereaux.mapping.target_format import parse_terms_file

router = APIRouter()


class TemplateColumn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    terms: list[str] = Field(default_factory=list, max_length=200)


class TemplateBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    columns: list[TemplateColumn] = Field(..., min_length=1, max_length=200)


def _columns(body: TemplateBody) -> list[dict[str, Any]]:
    return [c.model_dump() for c in body.columns]


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/format-templates", tags=["format-templates"])
async def get_format_templates(
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    templates = await list_templates(db)
    return envelope([serialize_template(t) for t in templates], request_id=_rid(request), total=len(templates))


@router.post("/format-templates/parse", tags=["format-templates"])
async def post_parse_format_file(
    request: Request,
    file: UploadFile = File(...),
    _user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_WRITE)),
) -> dict[str, Any]:
    """Read a CSV/TSV/XLSX (headers = columns, cells below = recognised terms). Nothing is saved."""
    return envelope(parse_terms_file(file.filename or "", await file.read()), request_id=_rid(request))


@router.post("/format-templates", tags=["format-templates"], status_code=201)
async def post_format_template(
    payload: TemplateBody,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    template = await create_template(db, user.id, payload.name, _columns(payload))
    return envelope(serialize_template(template), request_id=_rid(request))


@router.get("/format-templates/{template_id}", tags=["format-templates"])
async def get_format_template(
    template_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return envelope(serialize_template(await get_template(db, template_id)), request_id=_rid(request))


@router.put("/format-templates/{template_id}", tags=["format-templates"])
async def put_format_template(
    template_id: UUID,
    payload: TemplateBody,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    template = await update_template(db, template_id, user.id, payload.name, _columns(payload))
    return envelope(serialize_template(template), request_id=_rid(request))


@router.delete("/format-templates/{template_id}", tags=["format-templates"])
async def remove_format_template(
    template_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.FORMAT_TEMPLATE_WRITE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await delete_template(db, template_id, user.id)
    return envelope({"id": str(template_id), "deleted": True}, request_id=_rid(request))
