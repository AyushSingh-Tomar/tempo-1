"""processing_runs (NEW, iteration 1)

Revision ID: 007
Revises: 006
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RUN_STATUSES = (
    "'STARTED', 'FILE_UPLOADED', 'FILE_VALIDATED', 'CLEANING_COMPLETED', 'CLEANING_REVIEW_PENDING', "
    "'MAPPING_REVIEW_PENDING', 'MAPPING_CONFIRMED', 'TREATY_FIGURES_PENDING', 'TREATY_FIGURES_VALIDATED', "
    "'FINANCIAL_CHECKS_COMPLETED', 'DISCREPANCY_REVIEW_PENDING', 'REPORT_GENERATION_PENDING', "
    "'COMPLETED', 'FAILED'"
)


def upgrade() -> None:
    op.create_table(
        "processing_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("source_asset_id", sa.Uuid(), nullable=True),
        sa.Column("source_version_id", sa.Uuid(), nullable=True),
        sa.Column("mapping_set_id", sa.Uuid(), nullable=True),
        sa.Column("treaty_figures_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="STARTED"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_processing_runs")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_processing_runs_project_id_projects")),
        sa.ForeignKeyConstraint(["source_asset_id"], ["source_assets.id"], name=op.f("fk_processing_runs_source_asset_id_source_assets")),
        sa.ForeignKeyConstraint(["source_version_id"], ["source_versions.id"], name=op.f("fk_processing_runs_source_version_id_source_versions")),
        sa.ForeignKeyConstraint(["mapping_set_id"], ["mapping_sets.id"], name=op.f("fk_processing_runs_mapping_set_id_mapping_sets")),
        sa.ForeignKeyConstraint(["treaty_figures_id"], ["treaty_figures.id"], name=op.f("fk_processing_runs_treaty_figures_id_treaty_figures")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_processing_runs_created_by_users")),
        sa.CheckConstraint(f"status IN ({RUN_STATUSES})", name=op.f("ck_processing_runs_status")),
    )
    for col in (
        "project_id",
        "source_asset_id",
        "source_version_id",
        "mapping_set_id",
        "treaty_figures_id",
        "status",
        "created_by",
        "created_at",
    ):
        op.create_index(op.f(f"ix_processing_runs_{col}"), "processing_runs", [col])


def downgrade() -> None:
    op.drop_table("processing_runs")
