"""reconciliation workspace: recon_datasets, recon_files, recon_runs

Revision ID: 016
Revises: 015
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "recon_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("storage_path", sa.String(1000), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("column_count", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recon_datasets")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_recon_datasets_project_id_projects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_recon_datasets_created_by_users")),
        sa.CheckConstraint("kind IN ('BORDEREAUX', 'SUBLEDGER')", name=op.f("ck_recon_datasets_kind")),
        sa.CheckConstraint("status IN ('DRAFT', 'FINAL')", name=op.f("ck_recon_datasets_status")),
    )
    op.create_index(op.f("ix_recon_datasets_project_id"), "recon_datasets", ["project_id"])
    op.create_index(op.f("ix_recon_datasets_kind"), "recon_datasets", ["kind"])

    op.create_table(
        "recon_files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("encoding_info", sa.JSON(), nullable=True),
        sa.Column("encoding", sa.String(50), nullable=True),
        sa.Column("encoding_choice", sa.JSON(), nullable=False),
        sa.Column("sheets", sa.JSON(), nullable=False),
        sa.Column("selected_sheets", sa.JSON(), nullable=False),
        sa.Column("header_row", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recon_files")),
        sa.ForeignKeyConstraint(["dataset_id"], ["recon_datasets.id"], name=op.f("fk_recon_files_dataset_id_recon_datasets")),
    )
    op.create_index(op.f("ix_recon_files_dataset_id"), "recon_files", ["dataset_id"])

    op.create_table(
        "recon_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bordereaux_dataset_id", sa.Uuid(), nullable=False),
        sa.Column("subledger_dataset_id", sa.Uuid(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("result_path", sa.String(1000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recon_runs")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_recon_runs_project_id_projects")),
        sa.ForeignKeyConstraint(["bordereaux_dataset_id"], ["recon_datasets.id"], name=op.f("fk_recon_runs_bordereaux_dataset_id_recon_datasets")),
        sa.ForeignKeyConstraint(["subledger_dataset_id"], ["recon_datasets.id"], name=op.f("fk_recon_runs_subledger_dataset_id_recon_datasets")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_recon_runs_created_by_users")),
        sa.CheckConstraint("status IN ('RECONCILED', 'UNRECONCILED', 'FAILED')", name=op.f("ck_recon_runs_status")),
    )
    op.create_index(op.f("ix_recon_runs_project_id"), "recon_runs", ["project_id"])


def downgrade() -> None:
    for t in ("recon_runs", "recon_files", "recon_datasets"):
        op.drop_table(t)
