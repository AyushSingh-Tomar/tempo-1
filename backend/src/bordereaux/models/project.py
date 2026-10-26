"""users, projects (DATA_MODEL.md §3.1-3.2)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import ProjectStatus, UserRole
from bordereaux.models.base import Base, TimestampMixin, UUIDMixin, check_in, uuid_fk_type
from bordereaux.models.types import UTCDateTime


class User(UUIDMixin, TimestampMixin, Base):
    """Minimal user record. In iteration 1 rows are auto-provisioned from dev
    auth tokens (``external_id`` = the ``{user_id}`` part of ``dev-{user_id}-{role}``)."""

    __tablename__ = "users"
    __table_args__ = (
        check_in("role", UserRole.values()),
        Index("ix_users_email", "email"),
        Index("ix_users_external_id", "external_id"),
    )

    external_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default=UserRole.ANALYST.value, server_default=UserRole.ANALYST.value
    )
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        check_in("status", ProjectStatus.values()),
        Index(
            "ix_projects_status",
            "status",
            sqlite_where=text("deleted_at IS NULL"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_projects_created_by", "created_by"),
        Index("ix_projects_created_at", "created_at"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ProjectStatus.CREATED.value, server_default=ProjectStatus.CREATED.value
    )
    created_by: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
