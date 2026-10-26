"""discrepancy_findings, discrepancy_overrides (NEW for iteration 1).

Findings are shaped like ``diagnostic_findings`` (DATA_MODEL.md §3.12) but
``check_id`` is an MCR rule id (e.g. ``MCR-D1``) and ``category`` is an MCR
category.

Overrides are **append-only** and never mutate or delete the referenced
finding; at most one override per finding (unique ``discrepancy_id``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import DiscrepancyCategory, DiscrepancyStatus, Severity
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.immutability import register_append_only_table
from bordereaux.models.types import ExactDecimal


class DiscrepancyFinding(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "discrepancy_findings"
    __table_args__ = (
        check_in("category", DiscrepancyCategory.values()),
        check_in("severity", Severity.values()),
        check_in("status", DiscrepancyStatus.values()),
        Index("ix_discrepancy_findings_run_id", "run_id"),
        Index("ix_discrepancy_findings_check_id", "check_id"),
        Index("ix_discrepancy_findings_severity", "severity"),
        Index("ix_discrepancy_findings_status", "status"),
    )

    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    check_id: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    affected_row_number: Mapped[int | None] = mapped_column(Integer)
    affected_field: Mapped[str | None] = mapped_column(String(255))
    expected_value: Mapped[Decimal | None] = mapped_column(ExactDecimal(24, 6))
    observed_value: Mapped[Decimal | None] = mapped_column(ExactDecimal(24, 6))
    variance: Mapped[Decimal | None] = mapped_column(ExactDecimal(24, 6))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class DiscrepancyOverride(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "discrepancy_overrides"
    __append_only__ = True
    __table_args__ = (
        Index("ix_discrepancy_overrides_run_id", "run_id"),
        Index("ix_discrepancy_overrides_actor_id", "actor_id"),
    )

    discrepancy_id: Mapped[UUID] = mapped_column(
        uuid_fk_type(), ForeignKey("discrepancy_findings.id"), nullable=False, unique=True
    )
    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)


register_append_only_table(DiscrepancyOverride.__table__)
