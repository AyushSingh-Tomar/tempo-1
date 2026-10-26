"""user_ai_credentials: the API key a user chose to give the app for *their* AI calls.

The key is stored encrypted (Fernet, see ``bordereaux.ai.credentials``) and is never returned by
any endpoint - only ``key_hint`` (its last 4 characters) is, so the UI can show which key is active.
One row per user.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bordereaux.models.base import Base, TimestampMixin, UUIDMixin, uuid_fk_type
from bordereaux.models.types import UTCDateTime


class UserAICredential(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_ai_credentials"

    user_id: Mapped[UUID] = mapped_column(uuid_fk_type(), ForeignKey("users.id"), nullable=False, unique=True)
    encrypted_key: Mapped[str] = mapped_column(Text, nullable=False)
    key_hint: Mapped[str] = mapped_column(String(8), nullable=False)
    # Set when a live test call with this key succeeded; None = saved without a successful test.
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
