"""processing_runs.target_format - user-chosen target columns for mapping

Revision ID: 013
Revises: 012
Create Date: 2026-10-19
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch:
        batch.add_column(sa.Column("target_format", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("processing_runs") as batch:
        batch.drop_column("target_format")
