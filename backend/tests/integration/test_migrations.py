"""Alembic migrations: upgrade on a fresh SQLite file, zero drift vs. the models,
append-only triggers present, clean downgrade."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine as create_sync_engine

from bordereaux.models import Base

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _config(db_file: Path) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_file.as_posix()}")
    cfg.attributes["configure_logger"] = False
    return cfg


def test_upgrade_head_matches_models_and_downgrades(tmp_path: Path) -> None:
    db_file = tmp_path / "migrated.db"
    cfg = _config(db_file)

    command.upgrade(cfg, "head")

    with sqlite3.connect(db_file) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        triggers = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert set(Base.metadata.tables) <= tables
    assert version == "020"
    for table in ("audit_events", "treaty_figures", "discrepancy_overrides", "period_extract_artifacts"):
        assert {f"trg_{table}_no_update", f"trg_{table}_no_delete"} <= triggers

    engine = create_sync_engine(f"sqlite:///{db_file.as_posix()}")
    try:
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        engine.dispose()
    assert diff == [], f"models and migrations have drifted: {diff}"

    with sqlite3.connect(db_file) as conn:
        conn.execute(
            "INSERT INTO audit_events (id, timestamp, actor_type, event_type, action, target_type, target_id, metadata)"
            " VALUES ('a'||hex(randomblob(15)), CURRENT_TIMESTAMP, 'SYSTEM', 'x', 'CREATE', 'X', 'b', '{}')"
        )
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("UPDATE audit_events SET event_type = 'tampered'")
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            conn.execute("DELETE FROM audit_events")

    command.downgrade(cfg, "base")
    with sqlite3.connect(db_file) as conn:
        remaining = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert remaining <= {"alembic_version"}
