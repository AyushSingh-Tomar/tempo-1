"""audit_events (append-only, SECURITY_AND_AUDIT.md §5.3) and lineage_records (DATA_MODEL.md §3.15)

Revision ID: 012
Revises: 011
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

AUDIT = "audit_events"
LINEAGE_TYPES = (
    "'claims_mapping_row', 'subledger_row', 'variance_record', 'diagnostic_finding', "
    "'processed_row', 'discrepancy_finding', 'money_column_resolution'"
)


def upgrade() -> None:
    op.create_table(
        AUDIT,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("actor_type", sa.String(20), nullable=False),
        sa.Column("actor_ip", sa.String(45), nullable=True),
        sa.Column("actor_user_agent", sa.Text(), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("target_type", sa.String(100), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name=op.f("fk_audit_events_actor_id_users")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_audit_events_project_id_projects")),
        sa.CheckConstraint("actor_type IN ('USER', 'SYSTEM', 'AI')", name=op.f("ck_audit_events_actor_type")),
        sa.CheckConstraint(
            "action IN ('CREATE', 'READ', 'UPDATE', 'DELETE', 'APPROVE', 'REJECT', 'EXECUTE')",
            name=op.f("ck_audit_events_action"),
        ),
    )
    op.create_index(op.f("ix_audit_events_target"), AUDIT, ["target_type", "target_id"])
    op.create_index(op.f("ix_audit_events_actor_id"), AUDIT, ["actor_id"])
    op.create_index(op.f("ix_audit_events_project_id"), AUDIT, ["project_id"])
    op.create_index(op.f("ix_audit_events_timestamp"), AUDIT, ["timestamp"])
    op.create_index(op.f("ix_audit_events_event_type"), AUDIT, ["event_type"])

    if op.get_bind().dialect.name == "sqlite":
        op.execute(
            f"CREATE TRIGGER trg_{AUDIT}_no_update BEFORE UPDATE ON {AUDIT} "
            f"BEGIN SELECT RAISE(ABORT, '{AUDIT} is append-only'); END"
        )
        op.execute(
            f"CREATE TRIGGER trg_{AUDIT}_no_delete BEFORE DELETE ON {AUDIT} "
            f"BEGIN SELECT RAISE(ABORT, '{AUDIT} is append-only'); END"
        )
    else:  # pragma: no cover - PostgreSQL path, not exercised in iteration 1
        op.execute(f"REVOKE UPDATE, DELETE ON {AUDIT} FROM PUBLIC")

    op.create_table(
        "lineage_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(100), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("source_type", sa.String(100), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_row_number", sa.Integer(), nullable=True),
        sa.Column("transformation", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lineage_records")),
        sa.CheckConstraint(f"artifact_type IN ({LINEAGE_TYPES})", name=op.f("ck_lineage_records_artifact_type")),
    )
    op.create_index(op.f("ix_lineage_records_artifact"), "lineage_records", ["artifact_type", "artifact_id"])
    op.create_index(op.f("ix_lineage_records_source"), "lineage_records", ["source_type", "source_id"])


def downgrade() -> None:
    op.drop_table("lineage_records")
    if op.get_bind().dialect.name == "sqlite":
        op.execute(f"DROP TRIGGER IF EXISTS trg_{AUDIT}_no_update")
        op.execute(f"DROP TRIGGER IF EXISTS trg_{AUDIT}_no_delete")
    op.drop_table(AUDIT)
