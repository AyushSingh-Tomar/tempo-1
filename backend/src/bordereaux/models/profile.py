"""data_profiles, column_profiles (DATA_MODEL.md §3.5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import DataType
from bordereaux.core.utils import utcnow
from bordereaux.models.base import Base, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import ExactDecimal, UTCDateTime


class DataProfile(UUIDMixin, Base):
    __tablename__ = "data_profiles"
    __table_args__ = (
        UniqueConstraint("version_id", name="uq_data_profiles_version"),
        Index("ix_data_profiles_profile_job_id", "profile_job_id"),
    )

    version_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("source_versions.id"), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_job_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("jobs.id"))
    profiled_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, server_default=func.now()
    )


class ColumnProfile(UUIDMixin, Base):
    __tablename__ = "column_profiles"
    __table_args__ = (
        check_in("data_type", DataType.values()),
        UniqueConstraint("profile_id", "position", name="uq_column_profiles_position"),
        Index("ix_column_profiles_profile_id", "profile_id"),
        Index("ix_column_profiles_data_type", "data_type"),
    )

    profile_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("data_profiles.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    data_type: Mapped[str] = mapped_column(String(50), nullable=False)
    null_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    null_percentage: Mapped[Decimal] = mapped_column(
        ExactDecimal(5, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    distinct_count: Mapped[int] = mapped_column(Integer, nullable=False)
    distinct_percentage: Mapped[Decimal] = mapped_column(ExactDecimal(5, 4), nullable=False)
    top_values: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    numeric_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    string_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    date_stats: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    patterns: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
