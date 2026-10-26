"""jobs (DATA_MODEL.md §3.13, ADR-006)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import JobStatus, JobType
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import UTCDateTime


class Job(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        check_in("type", JobType.values()),
        check_in("status", JobStatus.values()),
        Index("ix_jobs_type", "type"),
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_project_id", "project_id"),
        Index("ix_jobs_created_at", "created_at"),
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=JobStatus.PENDING.value, server_default=JobStatus.PENDING.value
    )
    project_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"))
    input: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # {"percentage": int, "current_step": str|None, "total_steps": int|None, "message": str|None}
    progress: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=lambda: {"percentage": 0})
    # {"code": str, "message": str, "details": dict|None, "traceback": str|None}
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
