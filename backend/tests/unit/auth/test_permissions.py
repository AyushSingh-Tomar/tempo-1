"""The permission matrix must match SECURITY_AND_AUDIT.md §3.3 exactly."""

from __future__ import annotations

from uuid import uuid4

import pytest

from bordereaux.auth.permissions import (
    ROLE_PERMISSIONS,
    Permission,
    check_project_access,
    get_role_permissions,
    has_permission,
)
from bordereaux.core.models import UserRole

pytestmark = pytest.mark.unit

ROLES = ["admin", "project_owner", "analyst", "reviewer", "viewer"]

# Verbatim transcription of the §3.3 table: permission -> (admin, po, analyst, reviewer, viewer)
SPEC_MATRIX = {
    "project:create": (1, 1, 1, 0, 0),
    "project:read": (1, 1, 1, 1, 1),
    "project:update": (1, 1, 1, 0, 0),
    "project:delete": (1, 1, 0, 0, 0),
    "asset:upload": (1, 1, 1, 0, 0),
    "asset:read": (1, 1, 1, 1, 1),
    "asset:delete": (1, 1, 0, 0, 0),
    "mapping:generate": (1, 1, 1, 0, 0),
    "mapping:approve": (1, 1, 0, 1, 0),
    "mapping:reject": (1, 1, 0, 1, 0),
    "mapping:manual": (1, 1, 1, 0, 0),
    "reconciliation:create": (1, 1, 1, 0, 0),
    "reconciliation:read": (1, 1, 1, 1, 1),
    "report:generate": (1, 1, 1, 1, 0),
    "report:export": (1, 1, 1, 1, 1),
    "audit:read": (1, 0, 0, 0, 0),
    "user:manage": (1, 0, 0, 0, 0),
    "system:config": (1, 0, 0, 0, 0),
}

# Iteration-1 additions (proposal, not in spec)
ADDITIONS = {
    "run:create": (1, 1, 1, 0, 0),
    "run:read": (1, 1, 1, 1, 1),
    "discrepancy:read": (1, 1, 1, 1, 1),
    "discrepancy:override": (1, 1, 0, 1, 0),
    "treaty:create": (1, 1, 1, 0, 0),
    "treaty:update": (1, 1, 0, 0, 0),
    "treaty:approve": (1, 1, 0, 1, 0),
    "format_template:read": (1, 1, 1, 1, 1),
    "format_template:write": (1, 1, 1, 0, 0),
}


@pytest.mark.parametrize("perm", sorted({**SPEC_MATRIX, **ADDITIONS}))
def test_matrix_row(perm: str) -> None:
    expected = {**SPEC_MATRIX, **ADDITIONS}[perm]
    for role, allowed in zip(ROLES, expected):
        assert has_permission([role], perm) is bool(allowed), f"{role} / {perm}"


def test_every_permission_is_covered_by_tests() -> None:
    assert {p.value for p in Permission} == set(SPEC_MATRIX) | set(ADDITIONS)


def test_admin_has_everything() -> None:
    assert ROLE_PERMISSIONS[UserRole.ADMIN] == frozenset(Permission)


def test_unknown_roles_and_permissions() -> None:
    assert get_role_permissions(["superuser"]) == frozenset()
    assert has_permission(["admin"], "not:a:permission") is False
    assert get_role_permissions(["viewer", "analyst"]) == ROLE_PERMISSIONS[UserRole.VIEWER] | ROLE_PERMISSIONS[
        UserRole.ANALYST
    ]


def test_check_project_access() -> None:
    owner, other, member = uuid4(), uuid4(), uuid4()
    p = Permission.ASSET_UPLOAD
    assert check_project_access(other, ["admin"], owner, p) is True
    assert check_project_access(owner, ["analyst"], owner, p) is True
    assert check_project_access(other, ["analyst"], owner, p) is False
    assert check_project_access(member, ["analyst"], owner, p, member_ids={member}) is True
    assert check_project_access(owner, ["viewer"], owner, p) is False  # role lacks permission
    assert check_project_access(other, [UserRole.ADMIN], owner, p) is True
