"""cleaning_results (NEW for iteration 1).

One row per cleaning attempt - reruns insert a new row with the next
``attempt_number``; earlier attempts are preserved (status -> RETRIED).
Unique on (run_id, attempt_number), deliberately NOT unique on run_id.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import CleaningResultStatus
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type


class CleaningResult(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "cleaning_results"
    __table_args__ = (
        check_in("status", CleaningResultStatus.values()),
        UniqueConstraint("run_id", "attempt_number", name="uq_cleaning_results_run_attempt"),
        Index("ix_cleaning_results_run_id", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    before_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    before_column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    after_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    after_column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transformations: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=CleaningResultStatus.PENDING_REVIEW.value,
        server_default=CleaningResultStatus.PENDING_REVIEW.value,
    )
