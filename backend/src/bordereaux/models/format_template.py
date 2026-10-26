"""format_templates: named, reusable lists of final columns with their recognised terms.

A directory shared across the platform. A run that uses one stores a snapshot of
it (``processing_runs.target_format``), so changing or deleting a template never
alters a run that already used it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.models.base import Base, TimestampMixin, UUIDMixin, uuid_fk_type


class FormatTemplate(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "format_templates"
    __table_args__ = (
        UniqueConstraint("name_key"),
        Index("ix_format_templates_created_by", "created_by"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_key: Mapped[str] = mapped_column(String(100), nullable=False)  # normalised name: names are unique ignoring case/punctuation
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)  # [{"name": str, "terms": [str, ...]}, ...]
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
