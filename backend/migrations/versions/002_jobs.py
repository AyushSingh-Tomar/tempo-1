"""jobs (DATA_MODEL.md §3.13, ADR-006; job types extended for iteration 1)

Revision ID: 002
Revises: 001
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JOB_TYPES = (
    "'PARSE', 'PROFILE', 'GENERATE_MAPPINGS', 'STANDARDIZE', 'RECONCILE', 'REPORT', "
    "'VALIDATE', 'CLEAN', 'FINANCIAL_CHECKS', 'EXPORT'"
)
JOB_STATUSES = "'PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELLED'"


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="PENDING"),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("input", sa.JSON(), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_jobs_project_id_projects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_jobs_created_by_users")),
        sa.CheckConstraint(f"type IN ({JOB_TYPES})", name=op.f("ck_jobs_type")),
        sa.CheckConstraint(f"status IN ({JOB_STATUSES})", name=op.f("ck_jobs_status")),
    )
    op.create_index(op.f("ix_jobs_type"), "jobs", ["type"])
    op.create_index(op.f("ix_jobs_status"), "jobs", ["status"])
    op.create_index(op.f("ix_jobs_project_id"), "jobs", ["project_id"])
    op.create_index(op.f("ix_jobs_created_at"), "jobs", ["created_at"])


def downgrade() -> None:
    op.drop_table("jobs")
