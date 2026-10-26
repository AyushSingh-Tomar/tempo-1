"""Drive every provided test workbook through the real HTTP API:
upload -> validate -> clean -> acknowledge -> choose target format -> generate
-> review (approve exact / reject / manual) -> finalize -> treaty figures ->
financial checks. Asserts pipeline-wide invariants rather than per-file
expectations (those live in the focused unit tests)."""

from __future__ import annotations

from pathlib import Path

import httpx
import openpyxl
import pytest

from tests.conftest import auth

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files"
WORKBOOKS = sorted(FIXTURES.glob("*.xlsx")) if FIXTURES.exists() else []
TOKEN = "dev-admin1-admin"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

DEFAULT_TREATY = {
    "commission_pct": "0.25",
    "brokerage_pct": "0.0125",
    "tax_pct": "0.12",
    "cession_pct": "1.0",
    "order_pct": "1.0",
}


def _treaty_from_workbook(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    if "Treaty Figures" not in wb.sheetnames:
        return dict(DEFAULT_TREATY)
    values = {r[0]: r[1] for r in wb["Treaty Figures"].iter_rows(values_only=True) if r and r[0]}

    def pct(label: str, default: str) -> str:
        raw = values.get(label)
        if raw is None:
            return default
        text = str(raw).strip()
        return str(float(text.strip("%")) / 100) if text.endswith("%") else str(raw)

    return {
        "commission_pct": pct("Commission %", "0.25"),
        "brokerage_pct": pct("Brokerage %", "0.0125"),
        "tax_pct": pct("Tax / IPT %", "0.12"),
        "cession_pct": pct("Cession %", "1.0"),
        "order_pct": pct("Order %", "1.0"),
    }


async def _upload_and_map(client: httpx.AsyncClient, project, path: Path) -> str:
    content = path.read_bytes()
    url = f"/api/v1/projects/{project.id}/processing-runs"
    files = {"file": (path.name, content, XLSX)}
    resp = await client.post(url, files=files, headers=auth(TOKEN))
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    run_id = data["run"]["id"]
    base = f"/api/v1/processing-runs/{run_id}"
    sheets = data.get("available_sheets") or []
    sheet = next((s for s in sheets if s.startswith("Bordereaux")), None)
    r = await client.post(
        f"{base}/validate", params={"sheet_name": sheet} if sheet else None, headers=auth(TOKEN)
    )
    assert r.status_code == 200, (path.name, r.text)
    for step in ("clean", "cleaning/acknowledge"):
        r = await client.post(f"{base}/{step}", headers=auth(TOKEN))
        assert r.status_code == 200, (path.name, step, r.text)
    return run_id


@pytest.mark.skipif(not WORKBOOKS, reason="fixtures not present")
@pytest.mark.parametrize("path", WORKBOOKS, ids=lambda p: p.name)
async def test_workbook_end_to_end(client: httpx.AsyncClient, project, path: Path) -> None:
    run_id = await _upload_and_map(client, project, path)
    base = f"/api/v1/processing-runs/{run_id}"

    # Nothing is proposed before the user chooses a target format.
    r = await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))
    assert r.status_code == 200 and r.json()["data"]["candidates"] == []

    r = await client.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    r = await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))
    assert r.status_code == 200, (path.name, r.text)

    data = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    candidates = data["candidates"]
    assert candidates
    for c in candidates:
        assert "historical" not in c["confidence_breakdown"] and "relationship" not in c["confidence_breakdown"]
        assert c["target_field"] != "unresolved_money"
        if any(e.get("type") == "alias_match" and e.get("stage") == "EXACT" and e.get("score") == 1.0 for e in c["evidence"]) and not any(
            e.get("type") in ("duplicate_target_conflict", "ambiguous_alias") for e in c["evidence"]
        ):
            assert float(c["confidence_total"]) == 1.0, (path.name, c["source_column"])

    exact = [c for c in candidates if float(c["confidence_total"]) >= 1.0]
    extras = [c["source_column"] for c in candidates if c["target_field"].startswith("extra_")]
    other = [(c["source_column"], c["target_field"], round(float(c["confidence_total"]), 2)) for c in candidates
             if float(c["confidence_total"]) < 1.0 and not c["target_field"].startswith("extra_")]
    print(f"[{path.name}] columns={len({c['source_column'] for c in candidates})} exact100={len(exact)} "
          f"passthrough={extras} other={other}")

    # Bulk-approve the 100% matches, then settle everything still open.
    r = await client.post(f"{base}/mappings/approve-exact", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    data = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    for c in data["candidates"]:
        if c["status"] != "PROPOSED":
            continue
        loser = any(
            e.get("type") == "duplicate_target_conflict" and not e.get("winner", True) for e in c["evidence"]
        ) or any(e.get("type") == "ambiguous_alias" for e in c["evidence"])
        if loser:
            r = await client.post(f"/api/v1/mappings/{c['id']}/reject", json={"reason": "not it"}, headers=auth(TOKEN))
        else:
            r = await client.post(f"/api/v1/mappings/{c['id']}/approve", headers=auth(TOKEN))
        assert r.status_code in (200, 409), (path.name, c["source_column"], r.text)

    # Every source column ends up with exactly one decision.
    data = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    sources = {c["source_column"] for c in data["candidates"]}
    approved_sources = [m["source_column"] for m in data["approved_mappings"]]
    assert len(approved_sources) == len(set(approved_sources))

    r = await client.post(f"{base}/mappings/finalize", headers=auth(TOKEN))
    if r.status_code != 200:
        # Required fields present in the file but still unmapped is a legitimate block.
        assert r.status_code == 422 and "missing_fields" in r.text, (path.name, r.text)
        print(f"[{path.name}] finalize blocked: {r.json()['error']['details']}")
        return
    approved = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]["approved_mappings"]
    assert {m["source_column"] for m in approved} == sources

    derived = (await client.get(f"{base}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]
    body = {
        **_treaty_from_workbook(path),
        "settlement_currency": derived["settlement_currency"],
        "fx_rates": [
            {"currency": c["currency"], "rate": c["rate"] or "1", "source": "FILE" if c["rate"] else "USER"}
            for c in derived["currencies"]
        ],
    }
    r = await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))
    assert r.status_code == 201, (path.name, r.text)
    r = await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    assert r.status_code == 200, (path.name, r.text)
    assert "column_role_suggestions" in r.json()["data"]
    print(f"[{path.name}] checks={r.json()['data']['discrepancies_found']} suggestions={r.json()['data']['column_role_suggestions']}")
