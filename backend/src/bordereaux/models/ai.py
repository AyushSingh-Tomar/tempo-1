"""ai_interactions: one row per AI call, so the UI can always tell the user whether
AI was used for a run and, when it was not, exactly why (timeout, limit reached, ...).

The call itself is advisory (ADR-002: deterministic first); this table is the
visible record that it happened. Rows are written once and never edited.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type

AI_PURPOSES = ("MAPPING", "MONEY_RELATIONS")


class AIInteraction(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_interactions"
    __table_args__ = (
        check_in("purpose", AI_PURPOSES),
        Index("ix_ai_interactions_run_id", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    purpose: Mapped[str] = mapped_column(String(30), nullable=False)
    # ok | disabled | skipped | timeout | rate_limited | auth_error | unavailable | bad_response | invalid_request | error
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(50))
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer)
    items_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    items_resolved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
