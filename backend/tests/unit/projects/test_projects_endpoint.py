import httpx

from tests.conftest import auth


async def test_create_and_get_project(client: httpx.AsyncClient):
    resp = await client.post(
        "/api/v1/projects", json={"name": "Q3 2026 Reconciliation"}, headers=auth("dev-analyst1-analyst")
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()["data"]
    assert created["name"] == "Q3 2026 Reconciliation"
    assert created["status"] == "CREATED"

    get_resp = await client.get(f"/api/v1/projects/{created['id']}", headers=auth("dev-analyst1-analyst"))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == created["id"]


async def test_list_projects(client: httpx.AsyncClient):
    await client.post("/api/v1/projects", json={"name": "Project A"}, headers=auth("dev-analyst1-analyst"))
    await client.post("/api/v1/projects", json={"name": "Project B"}, headers=auth("dev-analyst1-analyst"))
    resp = await client.get("/api/v1/projects", headers=auth("dev-analyst1-analyst"))
    assert resp.status_code == 200
    names = [p["name"] for p in resp.json()["data"]]
    assert "Project A" in names and "Project B" in names


async def test_create_project_requires_permission(client: httpx.AsyncClient):
    resp = await client.post("/api/v1/projects", json={"name": "X"}, headers=auth("dev-viewer1-viewer"))
    assert resp.status_code == 403


async def test_get_unknown_project_404(client: httpx.AsyncClient):
    resp = await client.get(
        "/api/v1/projects/00000000-0000-0000-0000-000000000000", headers=auth("dev-analyst1-analyst")
    )
    assert resp.status_code == 404
