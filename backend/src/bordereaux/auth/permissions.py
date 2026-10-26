"""RBAC permissions and role matrix (SECURITY_AND_AUDIT.md §3.2-3.4).

The spec matrix (§3.3) is reproduced verbatim. Permissions marked
"ITERATION 1 ADDITION" are not in the spec and were added for the Bordereaux
Processing Accelerator workflow; their role assignment is a proposal the
coordinator may adjust.
"""

from __future__ import annotations

from enum import Enum
from typing import Collection, Iterable
from uuid import UUID

from bordereaux.core.models import UserRole


class Permission(str, Enum):
    # Project
    PROJECT_CREATE = "project:create"
    PROJECT_READ = "project:read"
    PROJECT_UPDATE = "project:update"
    PROJECT_DELETE = "project:delete"

    # Asset
    ASSET_UPLOAD = "asset:upload"
    ASSET_READ = "asset:read"
    ASSET_DELETE = "asset:delete"

    # Mapping
    MAPPING_GENERATE = "mapping:generate"
    MAPPING_APPROVE = "mapping:approve"
    MAPPING_REJECT = "mapping:reject"
    MAPPING_MANUAL = "mapping:manual"

    # Reconciliation
    RECONCILIATION_CREATE = "reconciliation:create"
    RECONCILIATION_READ = "reconciliation:read"

    # Report
    REPORT_GENERATE = "report:generate"
    REPORT_EXPORT = "report:export"

    # Treaty (spec: "Future"; TREATY_CREATE is used for treaty-figure entry in iteration 1)
    TREATY_CREATE = "treaty:create"
    TREATY_UPDATE = "treaty:update"
    TREATY_APPROVE = "treaty:approve"

    # Admin
    USER_MANAGE = "user:manage"
    SYSTEM_CONFIG = "system:config"
    AUDIT_READ = "audit:read"

    # ITERATION 1 ADDITION - processing runs & discrepancy review
    RUN_CREATE = "run:create"  # create a run / advance it (upload, clean, map, checks)
    RUN_READ = "run:read"
    DISCREPANCY_READ = "discrepancy:read"
    DISCREPANCY_OVERRIDE = "discrepancy:override"

    # ITERATION 1 ADDITION - saved final-format templates (platform-wide directory)
    FORMAT_TEMPLATE_READ = "format_template:read"
    FORMAT_TEMPLATE_WRITE = "format_template:write"  # create / rename / change columns and terms / delete

P = Permission
_ALL_ROLES = frozenset(UserRole)
_A, _PO, _AN, _RV, _VW = (
    UserRole.ADMIN,
    UserRole.PROJECT_OWNER,
    UserRole.ANALYST,
    UserRole.REVIEWER,
    UserRole.VIEWER,
)

# permission -> roles granted (mirrors the §3.3 table row by row)
_GRANTS: dict[Permission, frozenset[UserRole]] = {
    P.PROJECT_CREATE: frozenset({_A, _PO, _AN}),
    P.PROJECT_READ: _ALL_ROLES,
    P.PROJECT_UPDATE: frozenset({_A, _PO, _AN}),
    P.PROJECT_DELETE: frozenset({_A, _PO}),
    P.ASSET_UPLOAD: frozenset({_A, _PO, _AN}),
    P.ASSET_READ: _ALL_ROLES,
    P.ASSET_DELETE: frozenset({_A, _PO}),
    P.MAPPING_GENERATE: frozenset({_A, _PO, _AN}),
    P.MAPPING_APPROVE: frozenset({_A, _PO, _RV}),
    P.MAPPING_REJECT: frozenset({_A, _PO, _RV}),
    P.MAPPING_MANUAL: frozenset({_A, _PO, _AN}),
    P.RECONCILIATION_CREATE: frozenset({_A, _PO, _AN}),
    P.RECONCILIATION_READ: _ALL_ROLES,
    P.REPORT_GENERATE: frozenset({_A, _PO, _AN, _RV}),
    P.REPORT_EXPORT: _ALL_ROLES,
    P.AUDIT_READ: frozenset({_A}),
    P.USER_MANAGE: frozenset({_A}),
    P.SYSTEM_CONFIG: frozenset({_A}),
    # Treaty rows are not in the §3.3 table; proposal:
    P.TREATY_CREATE: frozenset({_A, _PO, _AN}),
    P.TREATY_UPDATE: frozenset({_A, _PO}),
    P.TREATY_APPROVE: frozenset({_A, _PO, _RV}),
    # ITERATION 1 ADDITIONS (proposal):
    P.RUN_CREATE: frozenset({_A, _PO, _AN}),
    P.RUN_READ: _ALL_ROLES,
    P.DISCREPANCY_READ: _ALL_ROLES,
    P.DISCREPANCY_OVERRIDE: frozenset({_A, _PO, _RV}),
    P.FORMAT_TEMPLATE_READ: _ALL_ROLES,
    P.FORMAT_TEMPLATE_WRITE: frozenset({_A, _PO, _AN}),  # same roles that can choose a target format
}

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    role: frozenset(perm for perm, roles in _GRANTS.items() if role in roles) for role in UserRole
}

# Admin has full system access by definition (§3.1).
ROLE_PERMISSIONS[UserRole.ADMIN] = frozenset(Permission)


def get_role_permissions(roles: Iterable[str | UserRole]) -> frozenset[Permission]:
    perms: set[Permission] = set()
    for role in roles:
        try:
            perms |= ROLE_PERMISSIONS[UserRole(role)]
        except ValueError:
            continue  # unknown roles grant nothing
    return frozenset(perms)


def has_permission(roles: Iterable[str | UserRole], permission: Permission | str) -> bool:
    try:
        perm = Permission(permission)
    except ValueError:
        return False
    return perm in get_role_permissions(roles)


def check_project_access(
    user_id: UUID,
    roles: Iterable[str | UserRole],
    project_owner_id: UUID,
    permission: Permission,
    member_ids: Collection[UUID] = (),
) -> bool:
    """Resource-level check per §3.4: admin always; otherwise the role must grant
    ``permission`` AND the user must own or be a member of the project.

    NOTE: there is no project-membership table yet, so ``member_ids`` is empty
    unless the caller supplies it - meaning only the owner and admins pass.
    """
    roles = list(roles)
    if UserRole.ADMIN.value in [str(getattr(r, "value", r)) for r in roles]:
        return True
    if not has_permission(roles, permission):
        return False
    return user_id == project_owner_id or user_id in member_ids
