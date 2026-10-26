from __future__ import annotations

import pytest

from bordereaux.auth.dev_provider import DevAuthProvider
from bordereaux.auth.service import AuthProvider
from bordereaux.models import User

pytestmark = pytest.mark.unit


def test_satisfies_protocol() -> None:
    assert isinstance(DevAuthProvider(), AuthProvider)


@pytest.mark.parametrize(
    ("token", "user_id", "role"),
    [
        ("dev-analyst1-analyst", "analyst1", "analyst"),
        ("Bearer dev-analyst1-analyst", "analyst1", "analyst"),
        ("dev-alice-project_owner", "alice", "project_owner"),
        ("dev-a.b_c-reviewer", "a.b_c", "reviewer"),
        ("dev-jane-doe-viewer", "jane-doe", "viewer"),  # hyphenated user id
        ("dev-root-admin", "root", "admin"),
    ],
)
async def test_valid_tokens(token: str, user_id: str, role: str) -> None:
    result = await DevAuthProvider().validate_token(token)
    assert result.valid is True
    assert result.error is None
    assert result.user_id == user_id
    assert result.roles == [role]
    assert result.expires_at is None
    assert result.permissions  # every role has at least read permissions


@pytest.mark.parametrize(
    ("token", "error"),
    [
        ("", "missing_token"),
        ("Bearer ", "missing_token"),
        ("dev-analyst1", "malformed_token"),
        ("dev-analyst1-superuser", "malformed_token"),  # unknown role
        ("prod-analyst1-analyst", "malformed_token"),
        ("dev--analyst", "malformed_token"),  # empty user id
        ("dev-bad user-analyst", "malformed_token"),
        ("dev-analyst1-ANALYST", "malformed_token"),  # roles are case-sensitive
        ("dev-x-analyst; DROP TABLE users", "malformed_token"),
    ],
)
async def test_invalid_tokens(token: str, error: str) -> None:
    result = await DevAuthProvider().validate_token(token)
    assert result.valid is False
    assert result.user_id is None
    assert result.roles == []
    assert result.permissions == []
    assert result.error == error


async def test_allow_list_enforced() -> None:
    provider = DevAuthProvider(allowed_tokens=["dev-analyst1-analyst", " "])
    assert (await provider.validate_token("dev-analyst1-analyst")).valid
    rejected = await provider.validate_token("dev-analyst2-analyst")
    assert rejected.valid is False
    assert rejected.error == "token_not_allowed"


async def test_viewer_permissions_are_read_only() -> None:
    result = await DevAuthProvider().validate_token("dev-v-viewer")
    assert "project:read" in result.permissions
    assert "asset:upload" not in result.permissions


def test_parse_token() -> None:
    assert DevAuthProvider.parse_token("dev-u1-analyst") == ("u1", "analyst")
    assert DevAuthProvider.parse_token("garbage") is None
    assert DevAuthProvider.parse_token(None) is None  # type: ignore[arg-type]


async def test_get_user(session_factory, db_session) -> None:
    provider = DevAuthProvider(session_factory=session_factory)
    assert await provider.get_user("ghost") is None

    db_session.add(User(external_id="known", email="known@dev.local", role="reviewer"))
    await db_session.commit()
    found = await provider.get_user("known")
    assert found is not None and found.role == "reviewer"

    assert await DevAuthProvider().get_user("known") is None  # no session factory
