"""ai_interactions (visible record of every AI call) and money_relations (user-declared money-column relationships)

Revision ID: 019
Revises: 018
Create Date: 2026-10-26
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_interactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("items_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("items_resolved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_interactions")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_ai_interactions_run_id_processing_runs")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_ai_interactions_created_by_users")),
        sa.CheckConstraint("purpose IN ('MAPPING', 'MONEY_RELATIONS')", name=op.f("ck_ai_interactions_purpose")),
    )
    op.create_index(op.f("ix_ai_interactions_run_id"), "ai_interactions", ["run_id"])

    op.create_table(
        "money_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("target_field", sa.String(255), nullable=False),
        sa.Column("terms", sa.JSON(), nullable=False),
        sa.Column("origin", sa.String(20), nullable=False, server_default="USER"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("last_rows_evaluated", sa.Integer(), nullable=True),
        sa.Column("last_rows_failed", sa.Integer(), nullable=True),
        sa.Column("last_skipped_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_money_relations")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_money_relations_run_id_processing_runs")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_money_relations_created_by_users")),
        sa.CheckConstraint("origin IN ('USER', 'STANDARD', 'AI_SUGGESTED')", name=op.f("ck_money_relations_origin")),
    )
    op.create_index(op.f("ix_money_relations_run_id"), "money_relations", ["run_id"])


def downgrade() -> None:
    op.drop_table("money_relations")
    op.drop_table("ai_interactions")
