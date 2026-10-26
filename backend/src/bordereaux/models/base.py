"""Declarative base and shared column mixins.

Conventions (DATA_MODEL.md §1.2):
- tables ``snake_case`` plural, UUID primary keys generated app-side via ``uuid4``
- indexes ``ix_{table}_{columns}``, FKs ``fk_{table}_{referenced_table}``,
  checks ``ck_{table}_{name}`` (applied automatically by the naming convention)
- UUIDs use SQLAlchemy's generic ``Uuid`` type: native ``UUID`` on PostgreSQL,
  ``CHAR(32)`` (hex, no dashes) on SQLite
- all timestamps are timezone-aware UTC (``UTCDateTime``)
- status vocabularies are ``String`` + ``CheckConstraint``, never native ENUMs
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, MetaData, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from bordereaux.core.utils import utcnow
from bordereaux.models.types import UTCDateTime

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDMixin:
    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, server_default=func.now()
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow, server_default=func.now()
    )


def uuid_fk_type() -> Uuid:
    return Uuid(as_uuid=True)


def check_in(column: str, values: Iterable[str], name: str | None = None) -> CheckConstraint:
    """``CHECK (column IN ('A','B',...))`` named ``ck_{table}_{name or column}``."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({quoted})", name=name or column)
