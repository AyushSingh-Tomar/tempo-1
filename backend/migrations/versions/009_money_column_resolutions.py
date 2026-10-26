"""money_column_resolutions (NEW, iteration 1)

Revision ID: 009
Revises: 008
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "money_column_resolutions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("source_column", sa.String(255), nullable=False),
        sa.Column("resolved_canonical_field", sa.String(255), nullable=True),
        sa.Column("resolution_stage", sa.String(50), nullable=False),
        sa.Column("matched_rules", sa.JSON(), nullable=False),
        sa.Column("is_ambiguous", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_column_resolutions")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_money_column_resolutions_run_id_processing_runs")),
        sa.CheckConstraint(
            "resolution_stage IN ('EXACT', 'FUZZY', 'SEMANTIC_ARITHMETIC', 'HUMAN_REVIEW', 'UNRESOLVED')",
            name=op.f("ck_money_column_resolutions_resolution_stage"),
        ),
    )
    op.create_index(op.f("ix_money_column_resolutions_run_id"), "money_column_resolutions", ["run_id"])
    op.create_index(op.f("ix_money_column_resolutions_source_column"), "money_column_resolutions", ["source_column"])


def downgrade() -> None:
    op.drop_table("money_column_resolutions")
