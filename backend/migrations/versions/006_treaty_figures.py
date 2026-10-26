"""treaty_figures (NEW, iteration 1) - immutable, insert-only

Revision ID: 006
Revises: 005
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from bordereaux.models.types import ExactDecimal

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "treaty_figures"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("commission_pct", ExactDecimal(12, 6), nullable=False),
        sa.Column("brokerage_pct", ExactDecimal(12, 6), nullable=True),
        sa.Column("tax_pct", ExactDecimal(12, 6), nullable=False),
        sa.Column("cession_pct", ExactDecimal(12, 6), nullable=False),
        sa.Column("order_pct", ExactDecimal(12, 6), nullable=True),
        sa.Column("fx_rate", ExactDecimal(18, 8), nullable=True),
        sa.Column("currency", sa.String(16), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_treaty_figures")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_treaty_figures_project_id_projects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_treaty_figures_created_by_users")),
    )
    op.create_index(op.f("ix_treaty_figures_project_id"), TABLE, ["project_id"])
    op.create_index(op.f("ix_treaty_figures_created_by"), TABLE, ["created_by"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            f"CREATE TRIGGER trg_{TABLE}_no_update BEFORE UPDATE ON {TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{TABLE} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{TABLE}_no_delete BEFORE DELETE ON {TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{TABLE} is append-only'); END"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_no_delete")
    op.drop_table(TABLE)
