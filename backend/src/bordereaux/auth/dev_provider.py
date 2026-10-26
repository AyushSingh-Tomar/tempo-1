"""Development-only authentication (SECURITY_AND_AUDIT.md §2.2).

    ##################################################################
    #  NOT FOR PRODUCTION.                                            #
    #  Tokens are static strings, there is no signature, no expiry,   #
    #  no session management and no refresh. Anyone who can guess a   #
    #  token format can claim any role. Replace with an OIDC provider #
    #  (same AuthProvider Protocol) before any non-local deployment.  #
    ##################################################################

Token format: ``dev-{user_id}-{role}``, sent as ``Authorization: Bearer dev-analyst1-analyst``.
``user_id`` may contain letters, digits, ``_``, ``.`` and ``-``; ``role`` must be
one of the five platform roles. If an allow-list is configured
(``DEV_AUTH_TOKENS``), only listed tokens are accepted.
"""

from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bordereaux.auth.permissions import get_role_permissions
from bordereaux.auth.service import AuthResult
from bordereaux.core.models import UserRole
from bordereaux.models.project import User

_ROLE_ALT = "|".join(sorted((r.value for r in UserRole), key=len, reverse=True))
DEV_TOKEN_RE = re.compile(rf"^dev-(?P<user_id>[A-Za-z0-9][A-Za-z0-9_.\-]{{0,99}})-(?P<role>{_ROLE_ALT})$")


class DevAuthProvider:
    def __init__(
        self,
        allowed_tokens: Iterable[str] | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._allowed = frozenset(t.strip() for t in (allowed_tokens or []) if t.strip())
        self._session_factory = session_factory

    @staticmethod
    def parse_token(token: str) -> tuple[str, str] | None:
        """Return ``(user_id, role)`` for a well-formed dev token, else None."""
        match = DEV_TOKEN_RE.match((token or "").strip())
        if not match:
            return None
        return match.group("user_id"), match.group("role")

    async def validate_token(self, token: str) -> AuthResult:
        token = (token or "").strip()
        scheme, _, rest = token.partition(" ")
        if scheme.lower() == "bearer":
            token = rest.strip()
        if not token:
            return AuthResult.invalid("missing_token")
        parsed = self.parse_token(token)
        if parsed is None:
            return AuthResult.invalid("malformed_token")
        if self._allowed and token not in self._allowed:
            return AuthResult.invalid("token_not_allowed")
        user_id, role = parsed
        perms = sorted(p.value for p in get_role_permissions([role]))
        return AuthResult(valid=True, user_id=user_id, roles=[role], permissions=perms, expires_at=None, error=None)

    async def get_user(self, user_id: str) -> User | None:
        if self._session_factory is None:
            return None
        async with self._session_factory() as session:
            result = await session.execute(select(User).where(User.external_id == user_id))
            return result.scalar_one_or_none()
