"""treaty_figures: settlement currency + per-currency FX rates

Revision ID: 014
Revises: 013
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # treaty_figures is append-only (SQLite triggers block UPDATE/DELETE, not ALTER).
    op.add_column("treaty_figures", sa.Column("settlement_currency", sa.String(16), nullable=True))
    op.add_column("treaty_figures", sa.Column("fx_rates", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("treaty_figures") as batch:
        batch.drop_column("fx_rates")
        batch.drop_column("settlement_currency")
