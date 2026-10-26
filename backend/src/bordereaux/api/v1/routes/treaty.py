"""Step 6/7: ``POST /api/v1/processing-runs/{run_id}/treaty-figures``."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.utils import envelope
from bordereaux.models.treaty import TreatyFigures
from bordereaux.treaty.schemas import TreatyFiguresRequest
from bordereaux.treaty.service import derive_for_run, submit_treaty_figures

router = APIRouter()


def serialize_treaty_figures(figures: TreatyFigures) -> dict[str, Any]:
    return {
        "id": str(figures.id),
        "project_id": str(figures.project_id),
        "commission_pct": str(figures.commission_pct),
        "brokerage_pct": str(figures.brokerage_pct) if figures.brokerage_pct is not None else None,
        "tax_pct": str(figures.tax_pct),
        "cession_pct": str(figures.cession_pct),
        "order_pct": str(figures.order_pct) if figures.order_pct is not None else None,
        "fx_rate": str(figures.fx_rate) if figures.fx_rate is not None else None,
        "currency": figures.currency,
        "settlement_currency": figures.settlement_currency,
        "expected_si_rate": str(figures.expected_si_rate) if figures.expected_si_rate is not None else None,
        "fx_rates": figures.fx_rates or [],
        "effective_from": figures.effective_from.isoformat() if figures.effective_from else None,
        "effective_to": figures.effective_to.isoformat() if figures.effective_to else None,
        "created_by": str(figures.created_by),
        "created_at": figures.created_at.isoformat() if figures.created_at else None,
    }


@router.post("/processing-runs/{run_id}/treaty-figures", tags=["treaty"], status_code=201)
async def post_treaty_figures(
    run_id: UUID,
    payload: TreatyFiguresRequest,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.TREATY_CREATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    figures = await submit_treaty_figures(db, run_id, payload, user.id, request.app.state.storage)
    return envelope(serialize_treaty_figures(figures), request_id=getattr(request.state, "request_id", None))


@router.get("/processing-runs/{run_id}/treaty-figures/derived", tags=["treaty"])
async def get_derived_treaty_inputs(
    run_id: UUID,
    request: Request,
    _user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Currencies (and FX rates, where the file has them) found in the mapped
    file, to pre-fill the treaty step as "derived from file". Editable there."""
    data = await derive_for_run(db, request.app.state.storage, run_id)
    return envelope(data, request_id=getattr(request.state, "request_id", None))
