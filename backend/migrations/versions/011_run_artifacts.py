"""processed_file_artifacts, audit_report_artifacts (NEW, iteration 1)

Revision ID: 011
Revises: 010
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ("processed_file_artifacts", "audit_report_artifacts")


def upgrade() -> None:
    for table in TABLES:
        op.create_table(
            table,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("run_id", sa.Uuid(), nullable=False),
            sa.Column("storage_path", sa.String(1000), nullable=False),
            sa.Column("format", sa.String(20), nullable=False),
            sa.Column("checksum", sa.String(128), nullable=False),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
            sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f(f"fk_{table}_run_id_processing_runs")),
        )
        op.create_index(op.f(f"ix_{table}_run_id"), table, ["run_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
