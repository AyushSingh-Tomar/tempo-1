"""Portable column types.

``UTCDateTime``
    SQLite has no timezone support; values come back naive. This decorator
    normalises everything to timezone-aware UTC on the way in *and* out, so
    application code always sees aware datetimes regardless of dialect.

``ExactDecimal``
    SQLite has no fixed-point type - SQLAlchemy's ``Numeric`` on SQLite stores
    floats, which is unacceptable for treaty percentages and money values
    ("deterministic first", ADR-002). On SQLite this stores the canonical
    decimal *string* (exact round-trip); on every other dialect (PostgreSQL)
    it is a native ``NUMERIC(precision, scale)``.

    Caveat on SQLite only: SQL-side ordering / SUM() over these columns is
    lexical, not numeric. Do arithmetic and ordering of money values in Python
    (which the MCR engine does anyway).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator, TypeEngine


class UTCDateTime(TypeDecorator[datetime]):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # Naive datetimes are assumed to already be UTC.
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class ExactDecimal(TypeDecorator[Decimal]):
    impl = Numeric
    cache_ok = True

    def __init__(self, precision: int = 24, scale: int = 6) -> None:
        super().__init__()
        self.precision = precision
        self.scale = scale

    def load_dialect_impl(self, dialect: Dialect) -> TypeEngine:
        if dialect.name == "sqlite":
            # precision digits + sign + decimal point + slack
            return dialect.type_descriptor(String(self.precision + 4))
        return dialect.type_descriptor(Numeric(self.precision, self.scale, asdecimal=True))

    def process_bind_param(self, value, dialect: Dialect):
        if value is None:
            return None
        if not isinstance(value, Decimal):
            if isinstance(value, float):
                # Go through repr() so 0.1 -> "0.1", not the binary expansion.
                value = Decimal(repr(value))
            else:
                try:
                    value = Decimal(str(value))
                except InvalidOperation as exc:
                    raise ValueError(f"Not a decimal value: {value!r}") from exc
        if not value.is_finite():
            raise ValueError(f"Non-finite decimal not allowed: {value!r}")
        if dialect.name == "sqlite":
            return format(value, "f")
        return value

    def process_result_value(self, value, dialect: Dialect) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))

    def __repr__(self) -> str:  # used by alembic autogenerate rendering
        return f"ExactDecimal(precision={self.precision}, scale={self.scale})"
