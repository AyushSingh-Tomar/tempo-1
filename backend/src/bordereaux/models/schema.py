"""canonical_schemas (DATA_MODEL.md §3.6).

The PK is a human-readable string id such as ``"bordereaux-pc-v1"`` (not a UUID).
``definition`` holds the full field dictionary as JSON; for iteration 1 it is
loaded from the versioned YAML config owned by the coordinator.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.core.models import SchemaStandard
from bordereaux.models.base import Base, TimestampMixin, check_in


class CanonicalSchema(TimestampMixin, Base):
    __tablename__ = "canonical_schemas"
    __table_args__ = (check_in("standard", SchemaStandard.values()),)

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    standard: Mapped[str] = mapped_column(
        String(50), nullable=False, default=SchemaStandard.CUSTOM.value, server_default=SchemaStandard.CUSTOM.value
    )
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
