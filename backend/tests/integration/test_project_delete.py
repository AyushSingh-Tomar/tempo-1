"""Deleting a project: project owners only, after typing the project's name; soft delete."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import httpx
import openpyxl
import pytest
from sqlalchemy import select

from bordereaux.models import AuditEvent
from bordereaux.models.project import Project
from tests.conftest import auth

pytestmark = pytest.mark.integration

OWNER = "dev-owner1-project_owner"
ANALYST = "dev-analyst1-analyst"
NAME = "Q3 2026 Bordereaux"


async def make_project(client: httpx.AsyncClient, name: str = NAME) -> str:
    r = await client.post("/api/v1/projects", json={"name": name}, headers=auth(ANALYST))
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


def delete(client: httpx.AsyncClient, project_id: str, confirm_name, token: str = OWNER):
    body = {} if confirm_name is None else {"confirm_name": confirm_name}
    return client.request("DELETE", f"/api/v1/projects/{project_id}", json=body, headers=auth(token))


async def names(client: httpx.AsyncClient) -> list[str]:
    return [p["name"] for p in (await client.get("/api/v1/projects", headers=auth(ANALYST))).json()["data"]]


async def test_a_project_owner_deletes_a_project_by_typing_its_name(client: httpx.AsyncClient, db_session):
    keep = await make_project(client, "Keep me")
    pid = await make_project(client)
    r = await delete(client, pid, f"  {NAME} ")  # surrounding spaces do not matter
    assert r.status_code == 200 and r.json()["data"] == {"id": pid, "deleted": True}

    assert await names(client) == ["Keep me"]
    assert (await client.get(f"/api/v1/projects/{pid}", headers=auth(ANALYST))).status_code == 404
    assert (await client.get(f"/api/v1/projects/{keep}", headers=auth(ANALYST))).status_code == 200
    assert (await delete(client, pid, NAME)).status_code == 404  # already gone

    # Soft delete: the record and its audit trail remain.
    db_session.expire_all()
    row = await db_session.get(Project, UUID(pid))
    assert row is not None and row.deleted_at is not None and row.status == "DELETED"
    events = (await db_session.execute(select(AuditEvent).where(AuditEvent.event_type == "project.deleted"))).scalars().all()
    assert len(events) == 1 and events[0].before_state["name"] == NAME and events[0].actor_id is not None
    assert events[0].project_id == row.id


@pytest.mark.parametrize("typed", ["", "   ", "q3 2026 bordereaux", "Q3 2026", NAME + "x", "Keep me"])
async def test_the_name_must_match_exactly(client: httpx.AsyncClient, typed: str):
    pid = await make_project(client)
    r = await delete(client, pid, typed)
    assert r.status_code == 400 and r.json()["error"]["code"] == "PROJECT_NAME_MISMATCH"
    assert NAME in await names(client)


async def test_no_confirmation_is_rejected(client: httpx.AsyncClient):
    pid = await make_project(client)
    assert (await delete(client, pid, None)).status_code == 400
    assert (await client.delete(f"/api/v1/projects/{pid}", headers=auth(OWNER))).status_code == 400
    assert NAME in await names(client)


@pytest.mark.parametrize("token", ["dev-admin1-admin", ANALYST, "dev-reviewer1-reviewer", "dev-viewer1-viewer"])
async def test_only_the_project_owner_role_may_delete(client: httpx.AsyncClient, db_session, token: str):
    pid = await make_project(client)
    r = await delete(client, pid, NAME, token)  # right name, wrong role
    assert r.status_code == 403
    assert NAME in await names(client)
    assert (await client.get(f"/api/v1/projects/{pid}", headers=auth(ANALYST))).status_code == 200
    denied = (await db_session.execute(select(AuditEvent).where(AuditEvent.event_type == "auth.permission_denied"))).scalars().all()
    assert any(e.metadata_.get("permission") == "project:delete" for e in denied)  # attempts are on record


async def test_a_deleted_project_accepts_no_new_work_and_can_be_recreated(client: httpx.AsyncClient, tmp_path: Path):
    pid = await make_project(client)
    assert (await delete(client, pid, NAME)).status_code == 200

    wb = openpyxl.Workbook()
    wb.active.title = "Bordereaux"
    wb.active.append(["UMR"])
    wb.active.append(["A1"])
    path = tmp_path / "x.xlsx"
    wb.save(path)
    r = await client.post(
        f"/api/v1/projects/{pid}/processing-runs",
        files={"file": ("x.xlsx", path.read_bytes(), "application/octet-stream")},
        headers=auth(ANALYST),
    )
    assert r.status_code == 404
    # The name can be used again for a new project.
    assert await make_project(client)
    assert await names(client) == [NAME]


async def test_unknown_project_is_404_for_the_owner(client: httpx.AsyncClient):
    assert (await delete(client, "00000000-0000-0000-0000-000000000000", NAME)).status_code == 404
