from __future__ import annotations

import pytest
from fastapi import APIRouter
from pydantic import BaseModel

from bordereaux.config import Settings
from bordereaux.core.exceptions import StateError

pytestmark = pytest.mark.unit


async def test_health_ok(client) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy", "checks": {"database": "ok", "storage": "ok"}}
    assert r.headers["x-request-id"].startswith("req_")


async def test_health_reports_database_failure(app, client, tmp_path) -> None:
    from bordereaux.core.database import create_engine

    old = app.state.engine
    # A directory path cannot be opened as a SQLite database file.
    bad_dir = tmp_path / "not-a-db"
    bad_dir.mkdir()
    app.state.engine = create_engine(f"sqlite+aiosqlite:///{bad_dir.as_posix()}")
    try:
        r = await client.get("/health")
    finally:
        await app.state.engine.dispose()
        app.state.engine = old
    assert r.status_code == 503
    assert r.json() == {"status": "unhealthy", "checks": {"database": "error", "storage": "ok"}}


async def test_incoming_request_id_is_honoured(client) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "trace-123"})
    assert r.headers["x-request-id"] == "trace-123"


class Body(BaseModel):
    name: str


@pytest.fixture
def error_app(app):
    router = APIRouter()

    @router.post("/boom/state")
    async def state():
        raise StateError("Run is not in MAPPING_CONFIRMED")

    @router.post("/boom/validate")
    async def validate(body: Body):
        return body

    @router.get("/boom/crash")
    async def crash():
        raise RuntimeError("db password is hunter2")

    app.include_router(router, prefix="/api/v1")
    return app


async def test_error_envelopes(error_app) -> None:
    import httpx

    transport = httpx.ASGITransport(app=error_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.post("/api/v1/boom/state")
        assert r.status_code == 409
        assert r.json()["error"] == {"code": "INVALID_STATE", "message": "Run is not in MAPPING_CONFIRMED", "details": []}

        r = await c.post("/api/v1/boom/validate", json={})
        assert r.status_code == 400
        err = r.json()["error"]
        assert err["code"] == "VALIDATION_ERROR" and err["details"][0]["field"] == "name"

        r = await c.get("/api/v1/does-not-exist")
        assert r.status_code == 404 and r.json()["error"]["code"] == "NOT_FOUND"

        r = await c.get("/api/v1/boom/crash")
        assert r.status_code == 500
        body = r.json()
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "hunter2" not in r.text
        assert body["meta"]["request_id"] in body["error"]["message"]


def test_create_app_rejects_unsupported_backends(tmp_path) -> None:
    from bordereaux.main import create_app

    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, storage_backend="s3", storage_root=tmp_path))
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, auth_provider="oidc", storage_root=tmp_path))


def test_lazy_module_app(monkeypatch, tmp_path) -> None:
    import bordereaux.main as main_mod

    monkeypatch.setenv("STORAGE_ROOT", str(tmp_path / "lazy"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{(tmp_path / 'lazy.db').as_posix()}")
    from bordereaux.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(main_mod, "_app", None)
    try:
        app = main_mod.app
        assert main_mod.app is app
        assert (tmp_path / "lazy").is_dir()
        with pytest.raises(AttributeError):
            main_mod.not_a_thing  # noqa: B018
    finally:
        get_settings.cache_clear()
