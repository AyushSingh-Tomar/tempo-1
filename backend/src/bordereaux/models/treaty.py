"""treaty_figures (NEW for iteration 1).

The six user-entered Group-J treaty figures. **Immutable**: a new submission
inserts a new row; existing rows are never updated or deleted (enforced by
the ORM guard and SQLite triggers - see ``immutability.py``). A processing run
points at exactly one row via ``processing_runs.treaty_figures_id``.

Percent columns store whatever representation the coordinator's validation
layer settles on (fraction 0.275 or percent 27.5); precision (12, 6) accommodates
both. Range validation is the caller's job - SQLite CHECKs cannot compare the
exact-decimal string storage numerically.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, uuid_fk_type
from bordereaux.models.immutability import register_append_only_table
from bordereaux.models.types import ExactDecimal


class TreatyFigures(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "treaty_figures"
    __append_only__ = True
    __table_args__ = (
        Index("ix_treaty_figures_project_id", "project_id"),
        Index("ix_treaty_figures_created_by", "created_by"),
    )

    project_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"), nullable=False)
    commission_pct: Mapped[Decimal] = mapped_column(ExactDecimal(12, 6), nullable=False)
    brokerage_pct: Mapped[Decimal | None] = mapped_column(ExactDecimal(12, 6))
    tax_pct: Mapped[Decimal] = mapped_column(ExactDecimal(12, 6), nullable=False)
    cession_pct: Mapped[Decimal] = mapped_column(ExactDecimal(12, 6), nullable=False)
    order_pct: Mapped[Decimal | None] = mapped_column(ExactDecimal(12, 6))
    fx_rate: Mapped[Decimal | None] = mapped_column(ExactDecimal(18, 8))
    currency: Mapped[str | None] = mapped_column(String(16))
    # Currency every amount is settled in; rates below convert *into* it.
    # Optional technical premium rate on sum insured (fraction); enables the MCR-D1 check.
    expected_si_rate: Mapped[Decimal | None] = mapped_column(ExactDecimal(12, 6))
    settlement_currency: Mapped[str | None] = mapped_column(String(16))
    # [{"currency": "GBP", "rate": "1.175", "source": "FILE"|"USER"}, ...]
    fx_rates: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)


register_append_only_table(TreatyFigures.__table__)
