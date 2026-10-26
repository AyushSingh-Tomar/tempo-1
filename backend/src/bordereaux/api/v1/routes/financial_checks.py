"""Step 8-10: run financial checks, review discrepancies, override, proceed."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.utils import envelope
from bordereaux.financial_checks.relations_service import (
    add_standard_relations,
    create_relation,
    delete_relation,
    get_relation_workspace,
    list_relations,
    serialize_relation,
    suggest_with_ai,
    update_relation,
)
from bordereaux.financial_checks.service import (
    list_discrepancies,
    override_discrepancy,
    proceed_to_report_generation,
    run_financial_checks,
)
from bordereaux.models.discrepancy import DiscrepancyFinding
from bordereaux.storage.service import StorageService

router = APIRouter()


def _get_storage(request: Request) -> StorageService:
    return request.app.state.storage


def serialize_finding(f: DiscrepancyFinding) -> dict[str, Any]:
    return {
        "id": str(f.id),
        "run_id": str(f.run_id),
        "check_id": f.check_id,
        "category": f.category,
        "severity": f.severity,
        "status": f.status,
        "affected_row_number": f.affected_row_number,
        "affected_field": f.affected_field,
        "expected_value": str(f.expected_value) if f.expected_value is not None else None,
        "observed_value": str(f.observed_value) if f.observed_value is not None else None,
        "variance": str(f.variance) if f.variance is not None else None,
        "evidence": f.evidence,
        "message": f.message,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


class OverrideRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    comment: str | None = None


@router.post("/processing-runs/{run_id}/financial-checks/run", tags=["financial-checks"])
async def post_run_financial_checks(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    result = await run_financial_checks(db, _get_storage(request), run_id, user.id)
    return envelope(result, request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/discrepancies", tags=["financial-checks"])
async def get_discrepancies(
    run_id: UUID,
    request: Request,
    severity: str | None = Query(None),
    status: str | None = Query(None),
    category: str | None = Query(None),
    _user: AuthenticatedUser = Depends(require_permission(Permission.DISCREPANCY_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from bordereaux.models.money_rules import MoneyColumnResolution

    findings = await list_discrepancies(db, run_id, severity=severity, status=status, category=category)
    resolutions = (
        await db.execute(select(MoneyColumnResolution).where(MoneyColumnResolution.run_id == run_id))
    ).scalars().all()
    return envelope(
        {
            "discrepancies": [serialize_finding(f) for f in findings],
            "total": len(findings),
            # The user-declared relations the checks were run against (with pass/fail counts).
            "relations": [serialize_relation(r) for r in await list_relations(db, run_id)],
            # Relationship check on columns that matched no dictionary field.
            "column_role_suggestions": [
                {
                    "source_column": r.source_column,
                    "suggested_field": r.resolved_canonical_field,
                    "is_ambiguous": r.is_ambiguous,
                    "matched_rules": [m.get("rule_id") for m in (r.matched_rules or []) if isinstance(m, dict)],
                }
                for r in resolutions
            ],
        },
        request_id=getattr(request.state, "request_id", None),
    )


@router.post("/discrepancies/{discrepancy_id}/override", tags=["financial-checks"])
async def post_override_discrepancy(
    discrepancy_id: UUID,
    payload: OverrideRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.DISCREPANCY_OVERRIDE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    override = await override_discrepancy(db, discrepancy_id, user.id, payload.reason, payload.comment)
    data = {
        "id": str(override.id),
        "discrepancy_id": str(override.discrepancy_id),
        "run_id": str(override.run_id),
        "actor_id": str(override.actor_id),
        "reason": override.reason,
        "comment": override.comment,
        "created_at": override.created_at.isoformat() if override.created_at else None,
    }
    return envelope(data, request_id=getattr(request.state, "request_id", None))


@router.post("/processing-runs/{run_id}/discrepancies/proceed", tags=["financial-checks"])
async def post_proceed_to_report_generation(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from bordereaux.api.v1.routes.runs import serialize_run

    run = await proceed_to_report_generation(db, run_id, user.id)
    return envelope(serialize_run(run), request_id=getattr(request.state, "request_id", None))


class TermPayload(BaseModel):
    field: str = Field(..., min_length=1)
    sign: int = Field(1)
    factors: list[str] = Field(default_factory=list)


class RelationPayload(BaseModel):
    label: str | None = Field(None, max_length=255)
    target_field: str = Field(..., min_length=1)
    terms: list[TermPayload] = Field(..., min_length=1)
    origin: str = Field("USER", pattern="^(USER|AI_SUGGESTED)$")
    rationale: str | None = Field(None, max_length=1000)

    def term_dicts(self) -> list[dict[str, Any]]:
        return [t.model_dump() for t in self.terms]


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("/processing-runs/{run_id}/money-relations", tags=["money-relations"])
async def get_money_relations(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Declared relations + the numeric columns and treaty figures a relation can use."""
    return envelope(await get_relation_workspace(db, _get_storage(request), run_id), request_id=_rid(request))


@router.post("/processing-runs/{run_id}/money-relations", tags=["money-relations"], status_code=201)
async def post_money_relation(
    run_id: UUID,
    payload: RelationPayload,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await create_relation(
        db,
        _get_storage(request),
        run_id,
        user.id,
        target_field=payload.target_field,
        terms=payload.term_dicts(),
        label=payload.label,
        origin=payload.origin,
        rationale=payload.rationale,
    )
    return envelope(serialize_relation(row), request_id=_rid(request))


@router.put("/processing-runs/{run_id}/money-relations/{relation_id}", tags=["money-relations"])
async def put_money_relation(
    run_id: UUID,
    relation_id: UUID,
    payload: RelationPayload,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    row = await update_relation(
        db,
        _get_storage(request),
        run_id,
        relation_id,
        user.id,
        target_field=payload.target_field,
        terms=payload.term_dicts(),
        label=payload.label,
    )
    return envelope(serialize_relation(row), request_id=_rid(request))


@router.delete("/processing-runs/{run_id}/money-relations/{relation_id}", tags=["money-relations"])
async def remove_money_relation(
    run_id: UUID,
    relation_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    await delete_relation(db, run_id, relation_id, user.id)
    return envelope({"deleted": str(relation_id)}, request_id=_rid(request))


@router.post("/processing-runs/{run_id}/money-relations/standard", tags=["money-relations"])
async def post_standard_money_relations(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add the standard premium-flow identities that fit this file's mapped columns (deterministic, no AI)."""
    return envelope(await add_standard_relations(db, _get_storage(request), run_id, user.id), request_id=_rid(request))


@router.post("/processing-runs/{run_id}/money-relations/ai-suggest", tags=["money-relations"])
async def post_ai_suggest_money_relations(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Ask the AI to propose relations. Always 200: an AI problem is reported in ``status``/``message``,
    never as an error, so the user can carry on declaring relations by hand."""
    return envelope(await suggest_with_ai(db, _get_storage(request), run_id, user.id), request_id=_rid(request))
