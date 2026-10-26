"""users and projects (DATA_MODEL.md §3.1-3.2)

Revision ID: 001
Revises:
Create Date: 2026-10-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = "'admin', 'project_owner', 'analyst', 'reviewer', 'viewer'"
PROJECT_STATUSES = "'CREATED', 'ACTIVE', 'ARCHIVED', 'DELETED'"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("role", sa.String(50), nullable=False, server_default="analyst"),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        sa.UniqueConstraint("external_id", name=op.f("uq_users_external_id")),
        sa.CheckConstraint(f"role IN ({ROLES})", name=op.f("ck_users_role")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"])
    op.create_index(op.f("ix_users_external_id"), "users", ["external_id"])

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="CREATED"),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_projects_created_by_users")),
        sa.CheckConstraint(f"status IN ({PROJECT_STATUSES})", name=op.f("ck_projects_status")),
    )
    op.create_index(
        op.f("ix_projects_status"),
        "projects",
        ["status"],
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(op.f("ix_projects_created_by"), "projects", ["created_by"])
    op.create_index(op.f("ix_projects_created_at"), "projects", ["created_at"])


def downgrade() -> None:
    op.drop_table("projects")
    op.drop_table("users")
