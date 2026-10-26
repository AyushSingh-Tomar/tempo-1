"""discrepancy_findings, discrepancy_overrides (NEW, iteration 1)

Overrides are append-only and never modify the referenced finding.

Revision ID: 010
Revises: 009
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from bordereaux.models.types import ExactDecimal

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIES = "'CORE_DEDUCTION', 'TREATY_RATIO', 'BASIS_ALIGNMENT', 'TRAP', 'TOTALS', 'SIGN'"
SEVERITIES = "'INFO', 'WARNING', 'ERROR', 'CRITICAL'"
STATUSES = "'CONFIRMED_ERROR', 'VALID_DIFFERENCE', 'WARNING', 'UNRESOLVED', 'OVERRIDDEN'"
OVERRIDES = "discrepancy_overrides"


def upgrade() -> None:
    op.create_table(
        "discrepancy_findings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("check_id", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("affected_row_number", sa.Integer(), nullable=True),
        sa.Column("affected_field", sa.String(255), nullable=True),
        sa.Column("expected_value", ExactDecimal(24, 6), nullable=True),
        sa.Column("observed_value", ExactDecimal(24, 6), nullable=True),
        sa.Column("variance", ExactDecimal(24, 6), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discrepancy_findings")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_discrepancy_findings_run_id_processing_runs")),
        sa.CheckConstraint(f"category IN ({CATEGORIES})", name=op.f("ck_discrepancy_findings_category")),
        sa.CheckConstraint(f"severity IN ({SEVERITIES})", name=op.f("ck_discrepancy_findings_severity")),
        sa.CheckConstraint(f"status IN ({STATUSES})", name=op.f("ck_discrepancy_findings_status")),
    )
    op.create_index(op.f("ix_discrepancy_findings_run_id"), "discrepancy_findings", ["run_id"])
    op.create_index(op.f("ix_discrepancy_findings_check_id"), "discrepancy_findings", ["check_id"])
    op.create_index(op.f("ix_discrepancy_findings_severity"), "discrepancy_findings", ["severity"])
    op.create_index(op.f("ix_discrepancy_findings_status"), "discrepancy_findings", ["status"])

    op.create_table(
        OVERRIDES,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discrepancy_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discrepancy_overrides")),
        sa.ForeignKeyConstraint(["discrepancy_id"], ["discrepancy_findings.id"], name=op.f("fk_discrepancy_overrides_discrepancy_id_discrepancy_findings")),
        sa.ForeignKeyConstraint(["run_id"], ["processing_runs.id"], name=op.f("fk_discrepancy_overrides_run_id_processing_runs")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_discrepancy_overrides_actor_id_users")),
        sa.UniqueConstraint("discrepancy_id", name=op.f("uq_discrepancy_overrides_discrepancy_id")),
    )
    op.create_index(op.f("ix_discrepancy_overrides_run_id"), OVERRIDES, ["run_id"])
    op.create_index(op.f("ix_discrepancy_overrides_actor_id"), OVERRIDES, ["actor_id"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            f"CREATE TRIGGER trg_{OVERRIDES}_no_update BEFORE UPDATE ON {OVERRIDES} "
            f"BEGIN SELECT RAISE(ABORT, '{OVERRIDES} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{OVERRIDES}_no_delete BEFORE DELETE ON {OVERRIDES} "
            f"BEGIN SELECT RAISE(ABORT, '{OVERRIDES} is append-only'); END"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{OVERRIDES}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{OVERRIDES}_no_delete")
    op.drop_table(OVERRIDES)
    op.drop_table("discrepancy_findings")
