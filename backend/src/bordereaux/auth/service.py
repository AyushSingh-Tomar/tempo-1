"""Authentication abstraction (SECURITY_AND_AUDIT.md §2.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable
from uuid import UUID

from bordereaux.auth.permissions import Permission


@dataclass(frozen=True)
class AuthResult:
    valid: bool
    user_id: str | None  # provider-level (external) user id, e.g. "analyst1"
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    expires_at: datetime | None = None
    error: str | None = None

    @classmethod
    def invalid(cls, error: str) -> "AuthResult":
        return cls(valid=False, user_id=None, roles=[], permissions=[], expires_at=None, error=error)


@dataclass(frozen=True)
class AuthenticatedUser:
    """What endpoint handlers receive from ``get_current_user``."""

    id: UUID  # users.id (internal UUID)
    external_id: str  # provider user id
    email: str
    name: str | None
    role: str
    permissions: frozenset[Permission]

    @property
    def roles(self) -> list[str]:
        return [self.role]

    def has(self, permission: Permission) -> bool:
        return permission in self.permissions


@runtime_checkable
class AuthProvider(Protocol):
    async def validate_token(self, token: str) -> AuthResult:
        """Validate token and return user info."""
        ...

    async def get_user(self, user_id: str) -> object | None:
        """Get user by provider (external) ID."""
        ...
