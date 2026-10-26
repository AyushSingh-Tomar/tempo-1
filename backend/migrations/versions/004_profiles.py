"""data_profiles and column_profiles (DATA_MODEL.md §3.5)

Revision ID: 004
Revises: 003
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from bordereaux.models.types import ExactDecimal

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DATA_TYPES = "'STRING', 'INTEGER', 'DECIMAL', 'BOOLEAN', 'DATE', 'DATETIME', 'UNKNOWN'"


def upgrade() -> None:
    op.create_table(
        "data_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("column_count", sa.Integer(), nullable=False),
        sa.Column("profile_job_id", sa.Uuid(), nullable=True),
        sa.Column("profiled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_profiles")),
        sa.ForeignKeyConstraint(["version_id"], ["source_versions.id"], name=op.f("fk_data_profiles_version_id_source_versions")),
        sa.ForeignKeyConstraint(["profile_job_id"], ["jobs.id"], name=op.f("fk_data_profiles_profile_job_id_jobs")),
        sa.UniqueConstraint("version_id", name=op.f("uq_data_profiles_version")),
    )
    op.create_index(op.f("ix_data_profiles_profile_job_id"), "data_profiles", ["profile_job_id"])

    op.create_table(
        "column_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("profile_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("null_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("null_percentage", ExactDecimal(5, 4), nullable=False, server_default="0"),
        sa.Column("distinct_count", sa.Integer(), nullable=False),
        sa.Column("distinct_percentage", ExactDecimal(5, 4), nullable=False),
        sa.Column("top_values", sa.JSON(), nullable=True),
        sa.Column("numeric_stats", sa.JSON(), nullable=True),
        sa.Column("string_stats", sa.JSON(), nullable=True),
        sa.Column("date_stats", sa.JSON(), nullable=True),
        sa.Column("patterns", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_column_profiles")),
        sa.ForeignKeyConstraint(["profile_id"], ["data_profiles.id"], name=op.f("fk_column_profiles_profile_id_data_profiles")),
        sa.UniqueConstraint("profile_id", "position", name=op.f("uq_column_profiles_position")),
        sa.CheckConstraint(f"data_type IN ({DATA_TYPES})", name=op.f("ck_column_profiles_data_type")),
    )
    op.create_index(op.f("ix_column_profiles_profile_id"), "column_profiles", ["profile_id"])
    op.create_index(op.f("ix_column_profiles_data_type"), "column_profiles", ["data_type"])


def downgrade() -> None:
    op.drop_table("column_profiles")
    op.drop_table("data_profiles")
