"""format_templates: named, reusable final-column formats with recognised terms

Revision ID: 018
Revises: 017
Create Date: 2026-10-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "format_templates"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_key", sa.String(100), nullable=False),
        sa.Column("columns", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f(f"fk_{TABLE}_created_by_users")),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f(f"fk_{TABLE}_updated_by_users")),
        sa.UniqueConstraint("name_key", name=op.f(f"uq_{TABLE}_name_key")),
    )
    op.create_index(op.f(f"ix_{TABLE}_created_by"), TABLE, ["created_by"])


def downgrade() -> None:
    op.drop_table(TABLE)
