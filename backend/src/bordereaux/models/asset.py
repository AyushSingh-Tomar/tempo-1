"""source_assets, source_versions (DATA_MODEL.md §3.3-3.4).

Raw files referenced by ``source_assets.storage_path`` are immutable (ADR-003);
re-parsing creates a new ``source_versions`` row with the next version_number.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, BigInteger, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import FileFormat, SourceAssetStatus, SourceVersionStatus
from bordereaux.models.base import Base, CreatedAtMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import UTCDateTime


class SourceAsset(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "source_assets"
    __table_args__ = (
        check_in("status", SourceAssetStatus.values()),
        check_in("format", FileFormat.values()),
        Index("ix_source_assets_project_id", "project_id"),
        Index("ix_source_assets_checksum", "checksum"),
        Index("ix_source_assets_format", "format"),
        Index("ix_source_assets_created_by", "created_by"),
    )

    project_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    format: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SourceAssetStatus.UPLOADED.value,
        server_default=SourceAssetStatus.UPLOADED.value,
    )
    # "metadata" is reserved on declarative classes, so the attribute is metadata_.
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON, default=dict)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class SourceVersion(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "source_versions"
    __table_args__ = (
        check_in("status", SourceVersionStatus.values()),
        UniqueConstraint("asset_id", "version_number", name="uq_source_versions_asset_version"),
        Index("ix_source_versions_asset_id", "asset_id"),
        Index("ix_source_versions_status", "status"),
        Index("ix_source_versions_parse_job_id", "parse_job_id"),
    )

    asset_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("source_assets.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=SourceVersionStatus.PARSED.value,
        server_default=SourceVersionStatus.PARSED.value,
    )
    # {"header_row", "data_start_row", "column_names", "detected_encoding", "detected_delimiter", "sheet_name"}
    structure: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    parse_errors: Mapped[list[Any] | None] = mapped_column(JSON, default=list)
    parse_job_id: Mapped[UUID | None] = mapped_column(uuid_fk_type(), ForeignKey("jobs.id"))
