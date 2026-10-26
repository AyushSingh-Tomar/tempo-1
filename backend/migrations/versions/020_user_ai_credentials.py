"""user_ai_credentials: per-user API key for AI calls, stored encrypted

Revision ID: 020
Revises: 019
Create Date: 2026-10-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_ai_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(8), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_ai_credentials")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_user_ai_credentials_user_id_users")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_ai_credentials_user_id")),
    )


def downgrade() -> None:
    op.drop_table("user_ai_credentials")
