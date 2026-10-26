"""FastAPI dependencies: ``get_current_user`` and ``require_permission(perm)``.

Usage::

    @router.post("/projects/{project_id}/processing-runs")
    async def create_run(
        user: AuthenticatedUser = Depends(require_permission(Permission.RUN_CREATE)),
        db: AsyncSession = Depends(get_db),
    ): ...

``get_current_user`` validates the bearer token with the configured
``AuthProvider`` (``app.state.auth_provider``) and maps the provider identity
to a ``users`` row, auto-provisioning it on first sight (audited as
``user.provisioned``). In dev mode the token's role is authoritative; a change
is written back to the row and audited as ``user.role_changed``.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.audit.service import AuditService
from bordereaux.auth.permissions import Permission, get_role_permissions
from bordereaux.auth.service import AuthenticatedUser, AuthProvider
from bordereaux.core.database import get_db
from bordereaux.core.exceptions import AuthenticationError, AuthorizationError
from bordereaux.core.models import ActorType, AuditAction
from bordereaux.core.utils import model_snapshot
from bordereaux.models.project import User


def get_auth_provider(request: Request) -> AuthProvider:
    return request.app.state.auth_provider


def _extract_bearer(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError("Authentication required")
    return token.strip()


async def _get_or_provision_user(db: AsyncSession, external_id: str, role: str) -> User:
    user = (await db.execute(select(User).where(User.external_id == external_id))).scalar_one_or_none()
    audit = AuditService(db)
    if user is None:
        user = User(external_id=external_id, email=f"{external_id}@dev.local", name=external_id, role=role)
        db.add(user)
        await db.flush()
        await audit.log(
            event_type="user.provisioned",
            target_type="User",
            target_id=user.id,
            action=AuditAction.CREATE,
            actor_id=None,
            actor_type=ActorType.SYSTEM,
            after_state=model_snapshot(user),
        )
    elif user.role != role:
        before = {"role": user.role}
        user.role = role
        await db.flush()
        await audit.log(
            event_type="user.role_changed",
            target_type="User",
            target_id=user.id,
            action=AuditAction.UPDATE,
            actor_id=None,
            actor_type=ActorType.SYSTEM,
            before_state=before,
            after_state={"role": role},
            reason="Role taken from dev auth token",
        )
    return user


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    provider: AuthProvider = Depends(get_auth_provider),
) -> AuthenticatedUser:
    token = _extract_bearer(request)
    result = await provider.validate_token(token)
    if not result.valid or not result.user_id or not result.roles:
        raise AuthenticationError("Authentication required", details={"reason": result.error or "invalid_token"})
    role = result.roles[0]
    user = await _get_or_provision_user(db, result.user_id, role)
    current = AuthenticatedUser(
        id=user.id,
        external_id=result.user_id,
        email=user.email,
        name=user.name,
        role=role,
        permissions=get_role_permissions([role]),
    )
    request.state.user = current
    return current


def require_permission(permission: Permission) -> Callable[..., Awaitable[AuthenticatedUser]]:
    """Dependency factory: 403 unless the current user's role grants ``permission``.

    Denials are audit-logged (``auth.permission_denied``) and committed before
    the 403 is raised, so the record survives the request rollback.
    """

    async def _dependency(
        request: Request,
        user: AuthenticatedUser = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> AuthenticatedUser:
        if permission in user.permissions:
            return user
        await AuditService(db).log(
            event_type="auth.permission_denied",
            target_type="Permission",
            target_id=user.id,
            action=AuditAction.READ,
            actor_id=user.id,
            actor_type=ActorType.USER,
            metadata={"permission": permission.value, "role": user.role, "path": request.url.path},
        )
        await db.commit()
        raise AuthorizationError("Permission denied")

    _dependency.__name__ = f"require_{permission.name.lower()}"
    return _dependency
