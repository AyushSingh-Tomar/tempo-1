"""period_extract_artifacts: the processed file narrowed to a year / quarter / month,
stored as immutable numbered versions (append-only).

Revision ID: 017
Revises: 016
Create Date: 2026-10-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLE = "period_extract_artifacts"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("storage_path", sa.String(1000), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("source_artifact_id", sa.Uuid(), nullable=False),
        sa.Column("source_checksum", sa.String(128), nullable=False),
        sa.Column("period_field", sa.String(100), nullable=False),
        sa.Column("period_label", sa.String(20), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("period_quarter", sa.Integer(), nullable=True),
        sa.Column("period_month", sa.Integer(), nullable=True),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("included_rows", sa.Integer(), nullable=False),
        sa.Column("included_partial_dates", sa.Integer(), nullable=False),
        sa.Column("excluded_outside_period", sa.Integer(), nullable=False),
        sa.Column("excluded_undated", sa.Integer(), nullable=False),
        sa.Column("generated_by", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{TABLE}")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f(f"fk_{TABLE}_run_id_processing_runs")),
        sa.ForeignKeyConstraint(
            ["source_artifact_id"],
            ["processed_file_artifacts.id"],
            name=op.f(f"fk_{TABLE}_source_artifact_id_processed_file_artifacts"),
        ),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], name=op.f(f"fk_{TABLE}_generated_by_users")),
        sa.UniqueConstraint(
            "run_id", "period_field", "period_label", "version_number",
            name=op.f(f"uq_{TABLE}_run_id_period_field_period_label_version_number"),
        ),
    )
    op.create_index(op.f(f"ix_{TABLE}_run_id"), TABLE, ["run_id"])
    op.create_index(op.f(f"ix_{TABLE}_lookup"), TABLE, ["run_id", "period_field", "period_label"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            f"CREATE TRIGGER trg_{TABLE}_no_update BEFORE UPDATE ON {TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{TABLE} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{TABLE}_no_delete BEFORE DELETE ON {TABLE} "
            f"BEGIN SELECT RAISE(ABORT, '{TABLE} is append-only'); END"
        )
    else:  # pragma: no cover - PostgreSQL path
        op.execute(f"REVOKE UPDATE, DELETE ON {TABLE} FROM PUBLIC")


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{TABLE}_no_delete")
    op.drop_table(TABLE)
