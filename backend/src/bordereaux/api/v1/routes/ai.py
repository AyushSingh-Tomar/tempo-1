"""AI transparency + control endpoints.

- ``GET    /ai/status``                               is AI usable for *me*, which model, whose key, and if not, why
- ``GET    /me/ai-key``                               my own key's state (never the key itself)
- ``PUT    /me/ai-key``                               give the app my API key (verified with a real call first)
- ``POST   /me/ai-key/test``                          re-test my stored key
- ``DELETE /me/ai-key``                               remove my key (the server's key, if any, is used again)
- ``GET    /processing-runs/{id}/ai/activity``        every AI call made for the run (status, reason, timing)
- ``POST   /processing-runs/{id}/mappings/ai-assist`` run the mapping AI step again (e.g. after a timeout)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.credentials import (
    InvalidKeyFormat,
    check_key,
    delete_user_key,
    get_credential,
    get_user_key,
    normalize_key,
    resolve_llm_service,
    save_user_key,
)
from bordereaux.ai.interactions import list_interactions, serialize_interaction
from bordereaux.ai.service import build_llm_service
from bordereaux.audit.service import AuditService
from bordereaux.auth.deps import get_current_user, require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import NotFoundError, ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import envelope
from bordereaux.mapping.service import retry_mapping_ai
from bordereaux.models.run import ProcessingRun

router = APIRouter()


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


async def _status_for(db: AsyncSession, user: AuthenticatedUser) -> dict[str, Any]:
    service, source = await resolve_llm_service(db, user.id, build_llm_service)
    cred = await get_credential(db, user.id)
    return {
        **service.status(),
        "key_source": source,  # "user" | "server" | "none"
        "user_key": {
            "configured": cred is not None,
            "hint": cred.key_hint if cred else None,
            "validated_at": cred.validated_at.isoformat() if cred and cred.validated_at else None,
        },
    }


@router.get("/ai/status", tags=["ai"])
async def get_ai_status(
    request: Request, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return envelope(await _status_for(db, user), request_id=_rid(request))


# ------------------------------------------------------------------ my API key


class ApiKeyPayload(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=600, repr=False)
    skip_test: bool = Field(False, description="Save without the live verification call")


def _test_result(outcome: Any) -> dict[str, Any]:
    return {k: outcome.to_dict()[k] for k in ("status", "message", "model", "latency_ms")}


@router.get("/me/ai-key", tags=["ai"])
async def get_my_ai_key(
    request: Request, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return envelope(await _status_for(db, user), request_id=_rid(request))


@router.put("/me/ai-key", tags=["ai"])
async def put_my_ai_key(
    payload: ApiKeyPayload,
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Verify the key with one real call, then store it encrypted. A key the provider rejects is not
    saved (``saved: false`` + the reason); ``skip_test`` stores it unverified."""
    try:
        key = normalize_key(payload.api_key)
    except InvalidKeyFormat as exc:
        raise ValidationError(str(exc)) from exc

    test: dict[str, Any] | None = None
    validated = False
    if not payload.skip_test:
        outcome = await check_key(key)
        test = _test_result(outcome)
        validated = outcome.ok
        if not outcome.ok:
            return envelope({"saved": False, "test": test, **await _status_for(db, user)}, request_id=_rid(request))

    await save_user_key(db, user.id, key, validated=validated)
    await AuditService(db).log(
        event_type="ai_key.set",
        target_type="User",
        target_id=user.id,
        action=AuditAction.UPDATE,
        actor_id=user.id,
        actor_type=ActorType.USER,
        after_state={"validated": validated},  # never the key, not even a fragment
    )
    await db.commit()
    return envelope({"saved": True, "test": test, **await _status_for(db, user)}, request_id=_rid(request))


@router.post("/me/ai-key/test", tags=["ai"])
async def post_test_my_ai_key(
    request: Request, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    key = await get_user_key(db, user.id)
    if key is None:
        raise NotFoundError("You have not saved an API key")
    outcome = await check_key(key)
    cred = await get_credential(db, user.id)
    if cred is not None and outcome.ok:
        from bordereaux.core.utils import utcnow

        cred.validated_at = utcnow()
        await db.commit()
    return envelope({"test": _test_result(outcome), **await _status_for(db, user)}, request_id=_rid(request))


@router.delete("/me/ai-key", tags=["ai"])
async def delete_my_ai_key(
    request: Request, user: AuthenticatedUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    removed = await delete_user_key(db, user.id)
    if removed:
        await AuditService(db).log(
            event_type="ai_key.removed",
            target_type="User",
            target_id=user.id,
            action=AuditAction.DELETE,
            actor_id=user.id,
            actor_type=ActorType.USER,
        )
    await db.commit()
    return envelope({"removed": removed, **await _status_for(db, user)}, request_id=_rid(request))


# ------------------------------------------------------------------ per-run activity


@router.get("/processing-runs/{run_id}/ai/activity", tags=["ai"])
async def get_ai_activity(
    run_id: UUID,
    request: Request,
    purpose: str | None = Query(None, pattern="^(MAPPING|MONEY_RELATIONS)$"),
    limit: int = Query(20, ge=1, le=100),
    user: AuthenticatedUser = Depends(require_permission(Permission.RUN_READ)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if await db.get(ProcessingRun, run_id) is None:
        raise NotFoundError("Processing run not found", details={"run_id": str(run_id)})
    rows = await list_interactions(db, run_id, purpose, limit)
    return envelope(
        {"ai": await _status_for(db, user), "interactions": [serialize_interaction(r) for r in rows]},
        request_id=_rid(request),
    )


@router.post("/processing-runs/{run_id}/mappings/ai-assist", tags=["ai"])
async def post_mapping_ai_assist(
    run_id: UUID,
    request: Request,
    user: AuthenticatedUser = Depends(require_permission(Permission.MAPPING_GENERATE)),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Always answers 200 with the outcome: an AI failure is data (``status``), not an HTTP error."""
    interaction = await retry_mapping_ai(db, request.app.state.storage, run_id, user.id)
    return envelope(interaction, request_id=_rid(request))
