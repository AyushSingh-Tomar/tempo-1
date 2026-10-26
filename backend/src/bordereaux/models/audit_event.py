"""audit_events, lineage_records.

``audit_events`` follows SECURITY_AND_AUDIT.md §5.3 (the newer, richer shape:
actor_type, action, target_type/target_id, request_id, reason) rather than the
older DATA_MODEL.md §3.14 shape (resource_type/resource_id). ``actor_id`` is
nullable because SYSTEM / AI events have no human actor.

Append-only: no UPDATE / DELETE is ever allowed (ORM guard + SQLite triggers).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import ActorType, AuditAction, LineageArtifactType
from bordereaux.core.utils import utcnow
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.immutability import register_append_only_table
from bordereaux.models.types import UTCDateTime


class AuditEvent(UUIDMixin, Base):
    __tablename__ = "audit_events"
    __append_only__ = True
    __table_args__ = (
        check_in("actor_type", ActorType.values()),
        check_in("action", AuditAction.values()),
        Index("ix_audit_events_target", "target_type", "target_id"),
        Index("ix_audit_events_actor_id", "actor_id"),
        Index("ix_audit_events_project_id", "project_id"),
        Index("ix_audit_events_timestamp", "timestamp"),
        Index("ix_audit_events_event_type", "event_type"),
    )

    timestamp: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, server_default=func.now()
    )
    actor_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_ip: Mapped[str | None] = mapped_column(String(45))
    actor_user_agent: Mapped[str | None] = mapped_column(Text)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    project_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"))
    request_id: Mapped[str | None] = mapped_column(String(100))
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False, default=dict)


register_append_only_table(AuditEvent.__table__)


class LineageRecord(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "lineage_records"
    __table_args__ = (
        check_in("artifact_type", LineageArtifactType.values()),
        Index("ix_lineage_records_artifact", "artifact_type", "artifact_id"),
        Index("ix_lineage_records_source", "source_type", "source_id"),
    )

    artifact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    artifact_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    source_row_number: Mapped[int | None] = mapped_column(Integer)
    transformation: Mapped[str | None] = mapped_column(String(255))
