"""get_current_user / require_permission through a real FastAPI app."""

from __future__ import annotations

import pytest
from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from bordereaux.auth.deps import require_permission
from bordereaux.auth.permissions import Permission
from bordereaux.auth.service import AuthenticatedUser
from bordereaux.models import AuditEvent, User

pytestmark = pytest.mark.unit


def H(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def guarded_app(app):
    router = APIRouter()

    @router.post("/guarded/upload")
    async def upload(user: AuthenticatedUser = Depends(require_permission(Permission.ASSET_UPLOAD))):
        return {"ok": True, "user": user.external_id}

    app.include_router(router, prefix="/api/v1")
    return app


async def test_me_requires_auth(client) -> None:
    r = await client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["WWW-Authenticate"] == "Bearer"
    body = r.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
    assert body["meta"]["request_id"].startswith("req_")


@pytest.mark.parametrize("header", [{"Authorization": "Basic abc"}, H("dev-x-wizard"), H("nonsense")])
async def test_me_rejects_bad_tokens(client, header) -> None:
    r = await client.get("/api/v1/me", headers=header)
    assert r.status_code == 401


async def test_me_provisions_user_once_and_audits(client, session_factory) -> None:
    r = await client.get("/api/v1/me", headers=H("dev-analyst7-analyst"))
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["external_id"] == "analyst7"
    assert data["role"] == "analyst"
    assert "asset:upload" in data["permissions"]
    assert "mapping:approve" not in data["permissions"]

    r2 = await client.get("/api/v1/me", headers=H("dev-analyst7-analyst"))
    assert r2.json()["data"]["id"] == data["id"]

    async with session_factory() as s:
        assert (await s.execute(select(func.count(User.id)).where(User.external_id == "analyst7"))).scalar_one() == 1
        events = (await s.execute(select(AuditEvent).where(AuditEvent.event_type == "user.provisioned"))).scalars().all()
        assert len(events) == 1
        assert events[0].request_id is not None


async def test_role_change_from_token_is_audited(client, session_factory) -> None:
    await client.get("/api/v1/me", headers=H("dev-sam-analyst"))
    r = await client.get("/api/v1/me", headers=H("dev-sam-reviewer"))
    assert r.json()["data"]["role"] == "reviewer"
    async with session_factory() as s:
        u = (await s.execute(select(User).where(User.external_id == "sam"))).scalar_one()
        assert u.role == "reviewer"
        ev = (await s.execute(select(AuditEvent).where(AuditEvent.event_type == "user.role_changed"))).scalar_one()
        assert ev.before_state == {"role": "analyst"} and ev.after_state == {"role": "reviewer"}


async def test_require_permission_allows(guarded_app, client) -> None:
    r = await client.post("/api/v1/guarded/upload", headers=H("dev-a1-analyst"))
    assert r.status_code == 200
    assert r.json() == {"ok": True, "user": "a1"}


async def test_require_permission_denies_and_audits(guarded_app, client, session_factory) -> None:
    r = await client.post("/api/v1/guarded/upload", headers=H("dev-v1-viewer"))
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "FORBIDDEN"
    assert r.json()["error"]["message"] == "Permission denied"  # no specifics leaked

    async with session_factory() as s:
        ev = (
            await s.execute(select(AuditEvent).where(AuditEvent.event_type == "auth.permission_denied"))
        ).scalar_one()
        assert ev.metadata_["permission"] == "asset:upload"
        assert ev.actor_type == "USER"
        # user provisioning was committed along with the denial record
        assert (await s.execute(select(User).where(User.external_id == "v1"))).scalar_one().role == "viewer"


async def test_require_permission_unauthenticated(guarded_app, client) -> None:
    r = await client.post("/api/v1/guarded/upload")
    assert r.status_code == 401


async def test_dev_token_allow_list(settings, engine) -> None:
    import httpx

    from bordereaux.main import create_app

    settings.dev_auth_tokens = "dev-ok-analyst"
    app = create_app(settings)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/v1/me", headers=H("dev-ok-analyst"))).status_code == 200
        assert (await c.get("/api/v1/me", headers=H("dev-other-analyst"))).status_code == 401
    await app.state.engine.dispose()
