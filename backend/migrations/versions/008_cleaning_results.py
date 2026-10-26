"""cleaning_results (NEW, iteration 1) - one row per cleaning attempt

Revision ID: 008
Revises: 007
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cleaning_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("before_row_count", sa.Integer(), nullable=False),
        sa.Column("before_column_count", sa.Integer(), nullable=False),
        sa.Column("after_row_count", sa.Integer(), nullable=False),
        sa.Column("after_column_count", sa.Integer(), nullable=False),
        sa.Column("transformations", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cleaning_results")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_cleaning_results_run_id_processing_runs")),
        sa.UniqueConstraint("run_id", "attempt_number", name=op.f("uq_cleaning_results_run_attempt")),
        sa.CheckConstraint(
            "status IN ('PENDING_REVIEW', 'ACKNOWLEDGED', 'RETRIED')", name=op.f("ck_cleaning_results_status")
        ),
    )
    op.create_index(op.f("ix_cleaning_results_run_id"), "cleaning_results", ["run_id"])


def downgrade() -> None:
    op.drop_table("cleaning_results")
