"""Async database engine / session factory and the ``get_db`` FastAPI dependency.

All DB access is async (SQLAlchemy 2.0 ``AsyncSession``). For SQLite we enable
``PRAGMA foreign_keys=ON`` on every connection - SQLite ignores FK constraints
otherwise.
"""

from __future__ import annotations

from typing import AsyncIterator

from fastapi import Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bordereaux.models.base import Base  # re-exported: the single declarative Base

__all__ = ["Base", "create_engine", "create_session_factory", "get_db", "check_database"]


def create_engine(database_url: str, echo: bool = False) -> AsyncEngine:
    kwargs: dict = {"echo": echo, "future": True}
    is_sqlite = database_url.startswith("sqlite")
    if is_sqlite:
        # Allow the connection to be used from the threadpool aiosqlite runs in,
        # and wait (not fail) briefly if another connection holds the write lock.
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
    engine = create_async_engine(database_url, **kwargs)

    if is_sqlite:

        @event.listens_for(engine.sync_engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record) -> None:  # pragma: no cover - exercised implicitly
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay usable after commit (needed for async,
    # where lazy refresh would otherwise trigger implicit IO).
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Commits on success, rolls back on any exception."""
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


async def check_database(engine: AsyncEngine) -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
