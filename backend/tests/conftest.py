"""Shared pytest fixtures.

- Each test gets its own temp-file SQLite database (a file, not ``:memory:``,
  so multiple connections - e.g. app + test session - see the same data).
- Schema comes from ``Base.metadata.create_all`` (fast). Migrations are
  verified separately in ``tests/integration/test_migrations.py``.
- ``storage`` is a ``LocalStorageService`` rooted in a temp directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncIterator

# Tests must never reach a real model, whatever backend/.env says (env vars beat the .env file).
os.environ["LLM_ENABLED"] = "false"
os.environ["LLM_PROVIDER"] = "disabled"
# Fixed master key so encrypted-credential tests never write a key file into the working tree.
os.environ["SECRETS_KEY"] = "kgZ4o8m0cYqTq3x3rK0zq5JrQ9cC1o2pZ3b7V8nXy0E="

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from bordereaux.config import Settings
from bordereaux.core.database import create_engine, create_session_factory
from bordereaux.models import Base, Project, User
from bordereaux.storage.local import LocalStorageService


def _sqlite_url(path: Path) -> str:
    return f"sqlite+aiosqlite:///{path.as_posix()}"


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return _sqlite_url(tmp_path / "test.db")


@pytest.fixture
async def engine(db_url: str) -> AsyncIterator[AsyncEngine]:
    eng = create_engine(db_url)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)


@pytest.fixture
async def db_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
def storage(tmp_path: Path) -> LocalStorageService:
    return LocalStorageService(tmp_path / "storage")


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    u = User(external_id="analyst1", email="analyst1@dev.local", name="Analyst One", role="analyst")
    db_session.add(u)
    await db_session.commit()
    return u


@pytest.fixture
async def project(db_session: AsyncSession, user: User) -> Project:
    p = Project(name="Test Project", created_by=user.id)
    db_session.add(p)
    await db_session.commit()
    return p


@pytest.fixture
def settings(tmp_path: Path, db_url: str) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=db_url,
        storage_root=tmp_path / "app-storage",
        dev_auth_tokens="",
    )


@pytest.fixture
async def app(settings: Settings, engine: AsyncEngine):
    # `engine` fixture ensures the schema exists in the same DB file.
    from bordereaux.main import create_app

    application = create_app(settings)
    yield application
    await application.state.engine.dispose()


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
