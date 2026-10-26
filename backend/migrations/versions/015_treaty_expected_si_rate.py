"""treaty_figures.expected_si_rate - optional technical premium rate on sum insured

Revision ID: 015
Revises: 014
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from bordereaux.models.types import ExactDecimal

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("treaty_figures", sa.Column("expected_si_rate", ExactDecimal(12, 6), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("treaty_figures") as batch:
        batch.drop_column("expected_si_rate")
