"""source_assets and source_versions (DATA_MODEL.md §3.3-3.4)

Revision ID: 003
Revises: 002
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ASSET_STATUSES = "'UPLOADED', 'PARSING', 'PARSED', 'FAILED', 'DELETED'"
FORMATS = "'CSV', 'TSV', 'XLSX', 'XLS', 'JSON', 'JSONL', 'PARQUET'"
VERSION_STATUSES = "'PARSED', 'PROFILED', 'MAPPED', 'STANDARDIZED', 'FAILED'"


def upgrade() -> None:
    op.create_table(
        "source_assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("format", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="UPLOADED"),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_assets")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_source_assets_project_id_projects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_source_assets_created_by_users")),
        sa.CheckConstraint(f"status IN ({ASSET_STATUSES})", name=op.f("ck_source_assets_status")),
        sa.CheckConstraint(f"format IN ({FORMATS})", name=op.f("ck_source_assets_format")),
    )
    op.create_index(op.f("ix_source_assets_project_id"), "source_assets", ["project_id"])
    op.create_index(op.f("ix_source_assets_checksum"), "source_assets", ["checksum"])
    op.create_index(op.f("ix_source_assets_format"), "source_assets", ["format"])
    op.create_index(op.f("ix_source_assets_created_by"), "source_assets", ["created_by"])

    op.create_table(
        "source_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PARSED"),
        sa.Column("structure", sa.JSON(), nullable=False),
        sa.Column("parse_errors", sa.JSON(), nullable=True),
        sa.Column("parse_job_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_versions")),
        sa.ForeignKeyConstraint(["asset_id"], ["source_assets.id"], name=op.f("fk_source_versions_asset_id_source_assets")),
        sa.ForeignKeyConstraint(["parse_job_id"], ["jobs.id"], name=op.f("fk_source_versions_parse_job_id_jobs")),
        sa.UniqueConstraint("asset_id", "version_number", name=op.f("uq_source_versions_asset_version")),
        sa.CheckConstraint(f"status IN ({VERSION_STATUSES})", name=op.f("ck_source_versions_status")),
    )
    op.create_index(op.f("ix_source_versions_asset_id"), "source_versions", ["asset_id"])
    op.create_index(op.f("ix_source_versions_status"), "source_versions", ["status"])
    op.create_index(op.f("ix_source_versions_parse_job_id"), "source_versions", ["parse_job_id"])


def downgrade() -> None:
    op.drop_table("source_versions")
    op.drop_table("source_assets")
