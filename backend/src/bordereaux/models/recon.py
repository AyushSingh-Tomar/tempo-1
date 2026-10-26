"""Reconciliation workspace: uploaded files, the combined ("final") datasets
built from them, and reconciliation runs. Raw files and finalized datasets are
immutable (ADR-003): a change means a new dataset, never an edit."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import UTCDateTime

DATASET_KINDS = ("BORDEREAUX", "SUBLEDGER")
DATASET_STATUSES = ("DRAFT", "FINAL")
RUN_STATUSES = ("RECONCILED", "UNRECONCILED", "FAILED")


class ReconDataset(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "recon_datasets"
    __table_args__ = (
        check_in("kind", DATASET_KINDS),
        check_in("status", DATASET_STATUSES),
        Index("ix_recon_datasets_project_id", "project_id"),
        Index("ix_recon_datasets_kind", "kind"),
    )

    project_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", server_default="DRAFT")
    # user choices: aliases, period column, day_first, drop duplicates
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    # report shown to the user: schema summary, years/quarters, warnings
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class ReconFile(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "recon_files"
    __table_args__ = (Index("ix_recon_files_dataset_id", "dataset_id"),)

    dataset_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("recon_datasets.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    # encoding decision (candidates, comparison) shown to the user
    encoding_info: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    encoding: Mapped[str | None] = mapped_column(String(50))
    encoding_choice: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)  # {forced, candidates}
    sheets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    selected_sheets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    header_row: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ReconRun(UUIDMixin, CreatedAtMixin, Base):
    __tablename__ = "recon_runs"
    __table_args__ = (
        check_in("status", RUN_STATUSES),
        Index("ix_recon_runs_project_id", "project_id"),
    )

    project_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    bordereaux_dataset_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("recon_datasets.id"), nullable=False)
    subledger_dataset_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("recon_datasets.id"), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)  # rules, group_by, filters, tolerance
    summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result_path: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
