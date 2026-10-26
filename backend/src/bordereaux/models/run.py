"""processing_runs (NEW for iteration 1).

The orchestrating entity of the Bordereaux Processing Accelerator workflow.
This module only defines the table. Legal status transitions are enforced by
the runs state machine (coordinator-owned) - nothing else should write
``status`` directly.
"""

from __future__ import annotations

from uuid import UUID

from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import ProcessingRunStatus
from bordereaux.models.base import Base, TimestampMixin, UUIDMixin, check_in, uuid_fk_type


class ProcessingRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "processing_runs"
    __table_args__ = (
        check_in("status", ProcessingRunStatus.values()),
        Index("ix_processing_runs_project_id", "project_id"),
        Index("ix_processing_runs_source_asset_id", "source_asset_id"),
        Index("ix_processing_runs_source_version_id", "source_version_id"),
        Index("ix_processing_runs_mapping_set_id", "mapping_set_id"),
        Index("ix_processing_runs_treaty_figures_id", "treaty_figures_id"),
        Index("ix_processing_runs_status", "status"),
        Index("ix_processing_runs_created_by", "created_by"),
        Index("ix_processing_runs_created_at", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"), nullable=False)
    source_asset_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("source_assets.id"))
    source_version_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("source_versions.id"))
    mapping_set_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("mapping_sets.id"))
    treaty_figures_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("treaty_figures.id"))
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=ProcessingRunStatus.STARTED.value,
        server_default=ProcessingRunStatus.STARTED.value,
    )
    # Target format chosen before mapping: None = default data dictionary,
    # else {"mode": "CUSTOM", "columns": [...], "fields": [resolved field defs]}.
    target_format: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
