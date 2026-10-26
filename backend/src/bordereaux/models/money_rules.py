"""money_column_resolutions (NEW for iteration 1).

Persistence only - the MCR rule engine that produces these rows is owned by
the coordinator (``bordereaux.money_rules``), not the foundation layer.
One row per source money column per run.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, ForeignKey, Index, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import ResolutionStage
from bordereaux.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, check_in, uuid_fk_type


class MoneyColumnResolution(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "money_column_resolutions"
    __table_args__ = (
        check_in("resolution_stage", ResolutionStage.values()),
        Index("ix_money_column_resolutions_run_id", "run_id"),
        Index("ix_money_column_resolutions_source_column", "source_column"),
    )

    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    source_column: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved_canonical_field: Mapped[str | None] = mapped_column(String(255))
    resolution_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    # [{"rule_id": "MCR-A1", "row_agreement": "0.97"}, ...]
    matched_rules: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


RELATION_ORIGINS = ("USER", "STANDARD", "AI_SUGGESTED")


class MoneyRelation(UUIDMixin, TimestampMixin, Base):
    """A money-column relationship the *user* declared for a run (Step 7):

        target_field  ~=  sum( sign * field * factor * factor ... )

    ``factors`` are treaty-figure names (``commission_pct``...) or decimal literals.
    ``origin`` records whether the user typed it, took it from the standard set or
    accepted an AI suggestion. Financial checks evaluate these deterministically; the
    ``last_*`` columns hold the outcome of the latest run for display.
    """

    __tablename__ = "money_relations"
    __table_args__ = (
        check_in("origin", RELATION_ORIGINS),
        Index("ix_money_relations_run_id", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("processing_runs.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    target_field: Mapped[str] = mapped_column(String(255), nullable=False)
    # [{"field": "gross_premium", "sign": 1, "factors": []}, {"field": "commission", "sign": -1, "factors": []}]
    terms: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="USER")
    rationale: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("users.id"))
    last_rows_evaluated: Mapped[int | None] = mapped_column(Integer)
    last_rows_failed: Mapped[int | None] = mapped_column(Integer)
    last_skipped_reason: Mapped[str | None] = mapped_column(Text)
