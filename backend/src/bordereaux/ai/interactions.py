"""Persistence of AI calls (``ai_interactions``) + audit trail.

Every AI attempt - successful, skipped by the user, unavailable or failed - leaves a
row so the UI can show whether AI was involved in a run and, if not, why. The
payload sent to the model is deliberately *not* stored (it can contain file data);
only counts, status and timing are.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.service import AIOutcome
from bordereaux.audit.service import AuditService
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.models.ai import AIInteraction
from bordereaux.models.run import ProcessingRun

AI_SKIPPED = "skipped"


def serialize_interaction(i: AIInteraction) -> dict[str, Any]:
    return {
        "id": str(i.id),
        "run_id": str(i.run_id),
        "purpose": i.purpose,
        "status": i.status,
        "message": i.message,
        "model": i.model,
        "provider": i.provider,
        "latency_ms": i.latency_ms,
        "timeout_seconds": i.timeout_seconds,
        "items_sent": i.items_sent,
        "items_resolved": i.items_resolved,
        "created_at": i.created_at.isoformat() if i.created_at else None,
    }


async def record_interaction(
    db: AsyncSession,
    run: ProcessingRun,
    *,
    purpose: str,
    outcome: AIOutcome | None = None,
    status: str | None = None,
    message: str | None = None,
    items_sent: int = 0,
    items_resolved: int = 0,
    actor_id: UUID | None = None,
) -> AIInteraction:
    """Insert (flushed, not committed) one interaction row and its audit event."""
    row = AIInteraction(
        run_id=run.id,
        purpose=purpose,
        status=status or (outcome.status if outcome else "error"),
        message=message if message is not None else (outcome.message if outcome else ""),
        model=outcome.model if outcome else None,
        provider=outcome.provider if outcome else None,
        latency_ms=outcome.latency_ms if outcome else 0,
        timeout_seconds=outcome.timeout_seconds if outcome else None,
        items_sent=items_sent,
        items_resolved=items_resolved,
        created_by=actor_id,
    )
    db.add(row)
    await db.flush()
    await AuditService(db).log(
        event_type=f"ai.{purpose.lower()}",
        target_type="ProcessingRun",
        target_id=run.id,
        action=AuditAction.EXECUTE,
        actor_id=actor_id,
        actor_type=ActorType.USER if actor_id else ActorType.SYSTEM,
        after_state={
            "status": row.status,
            "model": row.model,
            "latency_ms": row.latency_ms,
            "items_sent": items_sent,
            "items_resolved": items_resolved,
        },
        reason=row.message[:500] or None,
        project_id=run.project_id,
    )
    return row


async def list_interactions(
    db: AsyncSession, run_id: UUID, purpose: str | None = None, limit: int = 20
) -> list[AIInteraction]:
    stmt = select(AIInteraction).where(AIInteraction.run_id == run_id)
    if purpose:
        stmt = stmt.where(AIInteraction.purpose == purpose)
    stmt = stmt.order_by(AIInteraction.created_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
