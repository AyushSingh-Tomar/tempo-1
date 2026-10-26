"""Append-only audit logging (MODULE_CONTRACTS.md §2.2, SECURITY_AND_AUDIT.md §5).

``AuditService`` exposes exactly two operations - ``log`` (INSERT) and
``query`` (SELECT). It deliberately has no update/delete/remove methods, and
the ``audit_events`` table additionally rejects UPDATE/DELETE at the ORM and
database (trigger) level.

Transactions: ``log`` adds and flushes the event in the caller's session; the
caller's unit of work (e.g. the request-scoped ``get_db`` session) commits it
together with the state change being audited - so a rolled-back change never
leaves a dangling "it happened" audit row.

Request context (request_id, client IP, user agent, project) is picked up
automatically from ``bordereaux.core.context`` when not passed explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.core.context import get_request_context
from bordereaux.core.exceptions import ValidationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import to_jsonable, utcnow
from bordereaux.models.audit_event import AuditEvent

MAX_QUERY_LIMIT = 1000


class AuditServiceProtocol(Protocol):
    async def log(
        self,
        event_type: str,
        target_type: str,
        target_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
    ) -> AuditEvent: ...

    async def query(
        self,
        target_type: str | None = None,
        target_id: UUID | None = None,
        actor_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditEvent]: ...


class AuditService:
    """SQLAlchemy-backed append-only audit log."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        event_type: str,
        target_type: str,
        target_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        actor_type: ActorType = ActorType.SYSTEM,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
        *,
        reason: str | None = None,
        project_id: UUID | None = None,
    ) -> AuditEvent:
        """Insert one audit event and return it (flushed, not committed)."""
        if not event_type or not event_type.strip():
            raise ValidationError("event_type is required")
        if not target_type or not target_type.strip():
            raise ValidationError("target_type is required")
        if target_id is None:
            raise ValidationError("target_id is required")
        try:
            action_value = AuditAction(str(getattr(action, "value", action)).upper()).value
        except ValueError as exc:
            raise ValidationError(f"Invalid audit action: {action!r}") from exc
        try:
            actor_type_value = ActorType(str(getattr(actor_type, "value", actor_type)).upper()).value
        except ValueError as exc:
            raise ValidationError(f"Invalid actor_type: {actor_type!r}") from exc
        if actor_type_value == ActorType.USER.value and actor_id is None:
            raise ValidationError("actor_id is required when actor_type is USER")

        ctx = get_request_context()
        event = AuditEvent(
            timestamp=utcnow(),
            actor_id=actor_id,
            actor_type=actor_type_value,
            actor_ip=ctx.client_ip,
            actor_user_agent=ctx.user_agent,
            event_type=event_type.strip(),
            action=action_value,
            target_type=target_type.strip(),
            target_id=target_id,
            project_id=project_id if project_id is not None else ctx.project_id,
            request_id=ctx.request_id,
            before_state=to_jsonable(before_state) if before_state is not None else None,
            after_state=to_jsonable(after_state) if after_state is not None else None,
            reason=reason,
            metadata_=to_jsonable(metadata) if metadata else {},
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def query(
        self,
        target_type: str | None = None,
        target_id: UUID | None = None,
        actor_id: UUID | None = None,
        event_type: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        *,
        project_id: UUID | None = None,
    ) -> list[AuditEvent]:
        """Filtered events, newest first. ``since`` inclusive, ``until`` exclusive."""
        if limit < 1 or limit > MAX_QUERY_LIMIT:
            raise ValidationError(f"limit must be between 1 and {MAX_QUERY_LIMIT}")
        if offset < 0:
            raise ValidationError("offset must be >= 0")

        stmt = select(AuditEvent)
        if target_type is not None:
            stmt = stmt.where(AuditEvent.target_type == target_type)
        if target_id is not None:
            stmt = stmt.where(AuditEvent.target_id == target_id)
        if actor_id is not None:
            stmt = stmt.where(AuditEvent.actor_id == actor_id)
        if event_type is not None:
            stmt = stmt.where(AuditEvent.event_type == event_type)
        if project_id is not None:
            stmt = stmt.where(AuditEvent.project_id == project_id)
        if since is not None:
            stmt = stmt.where(AuditEvent.timestamp >= since)
        if until is not None:
            stmt = stmt.where(AuditEvent.timestamp < until)
        stmt = stmt.order_by(AuditEvent.timestamp.desc(), AuditEvent.id).limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())


def serialize_audit_event(event: AuditEvent) -> dict[str, Any]:
    """API-friendly dict for an audit event."""
    return {
        "id": str(event.id),
        "timestamp": event.timestamp.isoformat(),
        "actor_id": str(event.actor_id) if event.actor_id else None,
        "actor_type": event.actor_type,
        "actor_ip": event.actor_ip,
        "actor_user_agent": event.actor_user_agent,
        "event_type": event.event_type,
        "action": event.action,
        "target_type": event.target_type,
        "target_id": str(event.target_id),
        "project_id": str(event.project_id) if event.project_id else None,
        "request_id": event.request_id,
        "before_state": event.before_state,
        "after_state": event.after_state,
        "reason": event.reason,
        "metadata": event.metadata_,
    }
