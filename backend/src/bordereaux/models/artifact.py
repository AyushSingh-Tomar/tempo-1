"""processed_file_artifacts, audit_report_artifacts (NEW for iteration 1),
period_extract_artifacts.

Download endpoints must resolve files through these rows (never a raw path
from the client) so per-run / per-project access control is enforced.

A period extract is the processed file narrowed to one year / quarter / month.
Each generation is stored as a new immutable, numbered version (the table is
append-only) that records the processed file it was cut from.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from bordereaux.core.utils import utcnow
from bordereaux.models.base import Base, UUIDMixin, uuid_fk_type
from bordereaux.models.immutability import register_append_only_table
from bordereaux.models.types import UTCDateTime


class _RunArtifactMixin(UUIDMixin):
    @declared_attr
    def run_id(cls) -> Mapped[UUID]:  # noqa: N805
        return mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False, index=True)

    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, server_default=func.now()
    )


class ProcessedFileArtifact(_RunArtifactMixin, Base):
    __tablename__ = "processed_file_artifacts"


class AuditReportArtifact(_RunArtifactMixin, Base):
    __tablename__ = "audit_report_artifacts"


class PeriodExtractArtifact(_RunArtifactMixin, Base):
    __tablename__ = "period_extract_artifacts"
    __append_only__ = True
    __table_args__ = (
        UniqueConstraint("run_id", "period_field", "period_label", "version_number"),
        Index("ix_period_extract_artifacts_lookup", "run_id", "period_field", "period_label"),
    )

    source_artifact_id: Mapped[UUID] = mapped_column(
        uuid_fk_type(), ForeignKey("processed_file_artifacts.id"), nullable=False
    )
    source_checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    period_field: Mapped[str] = mapped_column(String(100), nullable=False)
    period_label: Mapped[str] = mapped_column(String(20), nullable=False)  # 2024 / 2024Q1 / 2024-03
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_quarter: Mapped[int | None] = mapped_column(Integer)
    period_month: Mapped[int | None] = mapped_column(Integer)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    included_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    included_partial_dates: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_outside_period: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_undated: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))


register_append_only_table(PeriodExtractArtifact.__table__)
