"""Small shared helpers (time, hashing, JSON-safe conversion, response envelope)."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import PurePath
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import inspect as sa_inspect


def utcnow() -> datetime:
    """Timezone-aware current UTC time. Use this everywhere instead of datetime.utcnow()."""
    return datetime.now(timezone.utc)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_request_id() -> str:
    return f"req_{uuid4().hex[:16]}"


def to_jsonable(value: Any) -> Any:
    """Recursively convert a value into something ``json.dumps`` accepts.

    - UUID -> str, datetime/date -> ISO-8601, Decimal -> str (exact, never float),
      Enum -> value, Path -> str, set/tuple -> list.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Enum):
        return to_jsonable(value.value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_jsonable(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return str(value)


def model_snapshot(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """JSON-safe dict of an ORM instance's column attributes - for audit
    ``before_state``/``after_state``. Keys are DB column names' attribute keys."""
    exclude = exclude or set()
    mapper = sa_inspect(obj).mapper
    out: dict[str, Any] = {}
    for attr in mapper.column_attrs:
        if attr.key in exclude:
            continue
        out[attr.key.rstrip("_")] = to_jsonable(getattr(obj, attr.key))
    return out


def envelope(data: Any, request_id: str | None = None, **meta: Any) -> dict[str, Any]:
    """Standard ``{data, meta}`` response envelope (ARCHITECTURE.md §5.2)."""
    return {
        "data": data,
        "meta": {"request_id": request_id, "timestamp": utcnow().isoformat(), **meta},
    }


def error_envelope(error: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Standard ``{error, meta}`` envelope (ARCHITECTURE.md §5.3)."""
    return {
        "error": error,
        "meta": {"request_id": request_id, "timestamp": utcnow().isoformat()},
    }
