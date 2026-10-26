"""Saved final-format templates: a platform-wide directory of named column lists with
their recognised terms, plus the logic that turns one into a run's target format.

Validation lives here (not in the route) so the HTTP API and any other caller get
the same rules. Names are unique ignoring case and punctuation.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.core.exceptions import ConflictError, NotFoundError, ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.mapping.aliasing import normalize_alias
from bordereaux.mapping.target_format import MAX_CUSTOM_COLUMNS, clean_terms
from bordereaux.models.format_template import FormatTemplate

MAX_TEMPLATE_NAME = 100
MAX_COLUMN_NAME = 200


def clean_name(raw: str) -> tuple[str, str]:
    """(display name, uniqueness key) of a template name. The key ignores case, spacing and all
    punctuation, so "Lloyd's Standard", "lloyds  standard" and "LLOYDS-STANDARD" are one name."""
    name = " ".join(str(raw or "").split())
    key = re.sub(r"[\W_]+", "", name.casefold())
    if not name or not key:
        raise ValidationError("A format needs a name")
    if len(name) > MAX_TEMPLATE_NAME:
        raise ValidationError(f"A format name can be at most {MAX_TEMPLATE_NAME} characters")
    return name, key[:MAX_TEMPLATE_NAME]


def clean_columns(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate ``[{"name": ..., "terms": [...]}, ...]``: names trimmed and unique (ignoring
    case and punctuation), terms trimmed and de-duplicated. Problems are errors, not silent fixes."""
    if not raw:
        raise ValidationError("A format needs at least one column")
    if len(raw) > MAX_CUSTOM_COLUMNS:
        raise ValidationError(f"At most {MAX_CUSTOM_COLUMNS} columns are supported")
    names: list[str] = []
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for item in raw:
        name = " ".join(str((item or {}).get("name", "")).split())
        key = normalize_alias(name)
        if not name or not key:
            raise ValidationError("Every column needs a name")
        if len(name) > MAX_COLUMN_NAME:
            raise ValidationError(f"A column name can be at most {MAX_COLUMN_NAME} characters")
        if key in seen:
            duplicates.append(name)
        seen[key] = name
        names.append(name)
    if duplicates:
        raise ValidationError("Column names must be unique", details={"duplicate_columns": duplicates})
    terms = clean_terms({n: list((item or {}).get("terms") or []) for n, item in zip(names, raw)}, names)
    return [{"name": n, "terms": terms.get(n, [])} for n in names]


def serialize_template(t: FormatTemplate) -> dict[str, Any]:
    columns = t.columns or []
    return {
        "id": str(t.id),
        "name": t.name,
        "columns": [{"name": c["name"], "terms": list(c.get("terms", []))} for c in columns],
        "column_count": len(columns),
        "term_count": sum(len(c.get("terms", [])) for c in columns),
        "created_by": str(t.created_by),
        "updated_by": str(t.updated_by) if t.updated_by else None,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def as_target_input(t: FormatTemplate) -> tuple[list[str], dict[str, list[str]]]:
    """The (columns, terms) a custom target format is built from."""
    columns = [c["name"] for c in t.columns]
    return columns, {c["name"]: list(c.get("terms", [])) for c in t.columns if c.get("terms")}


async def list_templates(db: AsyncSession) -> list[FormatTemplate]:
    stmt = select(FormatTemplate).order_by(FormatTemplate.name_key)
    return list((await db.execute(stmt)).scalars().all())


async def get_template(db: AsyncSession, template_id: UUID) -> FormatTemplate:
    template = await db.get(FormatTemplate, template_id)
    if template is None:
        raise NotFoundError("Format not found", details={"template_id": str(template_id)})
    return template


async def _assert_name_free(db: AsyncSession, key: str, own_id: UUID | None = None) -> None:
    existing = (await db.execute(select(FormatTemplate).where(FormatTemplate.name_key == key))).scalar_one_or_none()
    if existing is not None and existing.id != own_id:
        raise ConflictError(f"A format named '{existing.name}' already exists", code="FORMAT_NAME_TAKEN")


async def create_template(db: AsyncSession, actor_id: UUID, name: str, columns: list[dict[str, Any]]) -> FormatTemplate:
    display, key = clean_name(name)
    cleaned = clean_columns(columns)
    await _assert_name_free(db, key)
    template = FormatTemplate(name=display, name_key=key, columns=cleaned, created_by=actor_id, updated_by=actor_id)
    db.add(template)
    try:
        await db.flush()
    except IntegrityError as exc:  # two creators racing for the same name
        await db.rollback()
        raise ConflictError("A format with that name already exists", code="FORMAT_NAME_TAKEN") from exc
    await AuditService(db).log(
        event_type="format_template.created",
        target_type="FormatTemplate",
        target_id=template.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        after_state={"name": display, "columns": cleaned},
    )
    await db.commit()
    return template


async def update_template(
    db: AsyncSession, template_id: UUID, actor_id: UUID, name: str, columns: list[dict[str, Any]]
) -> FormatTemplate:
    """Replace a template's name and columns (rename, add/remove columns, change terms in one save)."""
    template = await get_template(db, template_id)
    display, key = clean_name(name)
    cleaned = clean_columns(columns)
    await _assert_name_free(db, key, own_id=template.id)
    before = {"name": template.name, "columns": template.columns}
    template.name, template.name_key, template.columns, template.updated_by = display, key, cleaned, actor_id
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("A format with that name already exists", code="FORMAT_NAME_TAKEN") from exc
    await AuditService(db).log(
        event_type="format_template.updated",
        target_type="FormatTemplate",
        target_id=template.id,
        action=AuditAction.UPDATE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state=before,
        after_state={"name": display, "columns": cleaned},
    )
    await db.commit()
    return template


async def delete_template(db: AsyncSession, template_id: UUID, actor_id: UUID) -> None:
    """Remove a template from the directory. Runs that already used it keep their own snapshot."""
    template = await get_template(db, template_id)
    before = {"name": template.name, "columns": template.columns}
    await db.delete(template)
    await db.flush()
    await AuditService(db).log(
        event_type="format_template.deleted",
        target_type="FormatTemplate",
        target_id=template_id,
        action=AuditAction.DELETE,
        actor_id=actor_id,
        actor_type=ActorType.USER,
        before_state=before,
    )
    await db.commit()
