"""mapping_sets, mapping_candidates, approved_mappings (DATA_MODEL.md §3.8).

Same shapes as the spec; JSONB -> JSON and DECIMAL -> ExactDecimal for SQLite.
``mapping_candidates.evidence`` may carry ``mcr_arithmetic`` / ``mcr_treaty_anchor``
entries (retained for older rows; relationship checks now run in financial checks).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, Text, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import MappingCandidateStatus, MappingOrigin, MappingSetStatus
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import ExactDecimal, UTCDateTime


class MappingSet(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "mapping_sets"
    __table_args__ = (
        check_in("status", MappingSetStatus.values()),
        Index("ix_mapping_sets_version_id", "version_id"),
        Index("ix_mapping_sets_status", "status"),
        Index("ix_mapping_sets_schema_id", "schema_id"),
        Index("ix_mapping_sets_generation_job_id", "generation_job_id"),
    )

    version_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("source_versions.id"), nullable=False)
    schema_id: Mapped[str] = mapped_column(String(100), ForeignKey("canonical_schemas.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=MappingSetStatus.DRAFT.value, server_default=MappingSetStatus.DRAFT.value
    )
    coverage_required: Mapped[Decimal | None] = mapped_column(ExactDecimal(5, 4))
    coverage_optional: Mapped[Decimal | None] = mapped_column(ExactDecimal(5, 4))
    generation_job_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("jobs.id"))
    finalized_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class MappingCandidate(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "mapping_candidates"
    __table_args__ = (
        check_in("status", MappingCandidateStatus.values()),
        Index("ix_mapping_candidates_set_id", "mapping_set_id"),
        Index("ix_mapping_candidates_status", "status"),
        Index("ix_mapping_candidates_source", "source_column"),
        Index("ix_mapping_candidates_confidence", "confidence_total"),
    )

    mapping_set_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("mapping_sets.id"), nullable=False)
    source_column: Mapped[str] = mapped_column(String(255), nullable=False)
    target_field: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence_total: Mapped[Decimal] = mapped_column(ExactDecimal(5, 4), nullable=False)
    confidence_breakdown: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evidence: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=MappingCandidateStatus.PROPOSED.value,
        server_default=MappingCandidateStatus.PROPOSED.value,
    )
    auto_approve_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    review_comment: Mapped[str | None] = mapped_column(Text)


class ApprovedMapping(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "approved_mappings"
    __table_args__ = (
        check_in("origin", MappingOrigin.values()),
        UniqueConstraint("mapping_set_id", "source_column", name="uq_approved_mappings_source"),
        Index("ix_approved_mappings_set_id", "mapping_set_id"),
        Index("ix_approved_mappings_candidate_id", "candidate_id"),
    )

    mapping_set_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("mapping_sets.id"), nullable=False)
    source_column: Mapped[str] = mapped_column(String(255), nullable=False)
    target_field: Mapped[str] = mapped_column(String(255), nullable=False)
    origin: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_total: Mapped[Decimal] = mapped_column(ExactDecimal(5, 4), nullable=False)
    transformation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    candidate_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("mapping_candidates.id"))
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
