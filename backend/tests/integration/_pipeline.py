"""Shared driver: upload -> clean -> map (default dictionary) -> finalize."""

from __future__ import annotations

from pathlib import Path

import httpx

from tests.conftest import auth

TOKEN = "dev-admin1-admin"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


async def upload_clean(client: httpx.AsyncClient, project, fixture: Path, sheet: str = "Bordereaux") -> str:
    """Upload -> validate -> clean -> acknowledge. Returns the run id."""
    url = f"/api/v1/projects/{project.id}/processing-runs"
    resp = await client.post(url, files={"file": (fixture.name, fixture.read_bytes(), XLSX)}, headers=auth(TOKEN))
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["data"]["run"]["id"]
    base = f"/api/v1/processing-runs/{run_id}"
    r = await client.post(f"{base}/validate", params={"sheet_name": sheet}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    for step in ("clean", "cleaning/acknowledge"):
        r = await client.post(f"{base}/{step}", headers=auth(TOKEN))
        assert r.status_code == 200, r.text
    return run_id


async def map_to_treaty_step(client: httpx.AsyncClient, project, fixture: Path, sheet: str = "Bordereaux") -> str:
    """Upload -> clean -> map (default dictionary) -> finalize. Returns the run id."""
    run_id = await upload_clean(client, project, fixture, sheet)
    base = f"/api/v1/processing-runs/{run_id}"
    r = await client.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    r = await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    r = await client.post(f"{base}/mappings/approve-exact", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    data = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    for c in data["candidates"]:
        if c["status"] != "PROPOSED":
            continue
        loser = any(
            e.get("type") == "duplicate_target_conflict" and not e.get("winner", True) for e in c["evidence"]
        ) or any(e.get("type") == "ambiguous_alias" for e in c["evidence"])
        path = "reject" if loser else "approve"
        body = {"reason": "not this field"} if loser else None
        r = await client.post(f"/api/v1/mappings/{c['id']}/{path}", json=body, headers=auth(TOKEN))
        assert r.status_code == 200, (c["source_column"], r.text)
    r = await client.post(f"{base}/mappings/finalize", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    return run_id


