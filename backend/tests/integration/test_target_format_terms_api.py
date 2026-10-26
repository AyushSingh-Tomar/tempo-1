"""Recognised terms for a custom final-column format, through the real HTTP API."""

from __future__ import annotations

from pathlib import Path

import httpx
import openpyxl
import pytest

from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

TOKEN = pipeline.TOKEN


@pytest.fixture
def source(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bordereaux"
    ws.append(["UMR", "Prime Brute", "Totally Other"])
    for i in range(1, 7):
        ws.append([f"B{i}2024XY000{i}", 1000 * i, f"x{i}"])
    path = tmp_path / "terms_source.xlsx"
    wb.save(path)
    return path


async def start(client: httpx.AsyncClient, project, source: Path) -> str:
    run_id = await pipeline.upload_clean(client, project, source)
    return f"/api/v1/processing-runs/{run_id}"


async def put_format(client: httpx.AsyncClient, base: str, **body):
    return await client.put(f"{base}/mappings/target-format", json=body, headers=auth(TOKEN))


async def generate(client: httpx.AsyncClient, base: str) -> dict[str, dict]:
    assert (await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))).status_code == 200
    data = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    return {c["source_column"]: c for c in data["candidates"]}


async def test_default_format_exposes_the_built_in_recognised_terms(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)
    data = (await client.get(f"{base}/mappings/target-format", headers=auth(TOKEN))).json()["data"]
    assert data["mode"] == "DEFAULT" and data["selected"] is False
    gross = next(f for f in data["fields"] if f["name"] == "gross_premium")
    assert "GWP" in gross["recognised_terms"] and gross["user_terms"] == []


async def test_user_terms_decide_the_mapping_and_the_default_path_is_unchanged(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)

    # Without terms, "Prime Brute" is nothing the dictionary knows: it passes through untouched.
    assert (await put_format(client, base, mode="CUSTOM", columns=["UMR", "Premium Due"])).status_code == 200
    plain = await generate(client, base)
    assert plain["Prime Brute"]["target_field"].startswith("extra_")

    # With the user's own terms it maps at 100% (and, since GWP is a known term, keeps its money meaning).
    r = await put_format(client, base, mode="CUSTOM", columns=["UMR", "Premium Due"], terms={"Premium Due": ["GWP", "Prime Brute"]})
    assert r.status_code == 200, r.text
    fields = {f["display_name"]: f for f in r.json()["data"]["fields"]}
    assert fields["Premium Due"]["name"] == "gross_premium" and fields["Premium Due"]["user_terms"] == ["GWP", "Prime Brute"]
    mapped = await generate(client, base)
    cand = mapped["Prime Brute"]
    assert cand["target_field"] == "gross_premium" and float(cand["confidence_total"]) == 1.0
    assert any(e["type"] == "alias_match" and e["stage"] == "EXACT" for e in cand["evidence"])
    assert mapped["UMR"]["target_field"] == "umr" and mapped["Totally Other"]["target_field"].startswith("extra_")

    # The usual review and finalize still work on top of it.
    assert (await client.post(f"{base}/mappings/approve-exact", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/mappings/finalize", headers=auth(TOKEN))).status_code == 200
    approved = {m["source_column"]: m["target_field"] for m in (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]["approved_mappings"]}
    assert approved["Prime Brute"] == "gross_premium"


async def test_switching_back_to_default_drops_the_user_terms(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)
    await put_format(client, base, mode="CUSTOM", columns=["Premium Due"], terms={"Premium Due": ["Prime Brute"]})
    back = (await put_format(client, base, mode="DEFAULT")).json()["data"]
    assert back["mode"] == "DEFAULT" and all(f["user_terms"] == [] for f in back["fields"])
    mapped = await generate(client, base)
    assert mapped["Prime Brute"]["target_field"].startswith("extra_")  # the default dictionary does not know it


async def test_terms_are_validated(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)
    r = await put_format(client, base, mode="DEFAULT", terms={"Gross Premium": ["GWP"]})
    assert r.status_code == 400 and "own final columns" in r.text
    r = await put_format(client, base, mode="CUSTOM", columns=["UMR"], terms={"Not A Column": ["x"]})
    assert r.status_code == 400 and "Not A Column" in r.text
    r = await put_format(client, base, mode="CUSTOM", columns=["UMR"], terms={"UMR": ["x" * 201]})
    assert r.status_code == 400
    # A rejected request leaves the previous choice in force.
    assert (await client.get(f"{base}/mappings/target-format", headers=auth(TOKEN))).json()["data"]["selected"] is False


async def test_the_terms_file_fills_the_form_and_saves_nothing(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)
    csv_bytes = b"UMR,Premium Due\n,GWP\n,Prime Brute\n"
    r = await client.post(f"{base}/mappings/target-format/parse-terms", files={"file": ("terms.csv", csv_bytes, "text/csv")}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    assert r.json()["data"] == {"columns": ["UMR", "Premium Due"], "terms": {"Premium Due": ["GWP", "Prime Brute"]}, "skipped_terms": 0}
    assert (await client.get(f"{base}/mappings/target-format", headers=auth(TOKEN))).json()["data"]["selected"] is False

    bad = await client.post(f"{base}/mappings/target-format/parse-terms", files={"file": ("terms.txt", b"a", "text/plain")}, headers=auth(TOKEN))
    assert bad.status_code == 400
    # The parsed result is exactly what the format endpoint accepts.
    parsed = r.json()["data"]
    ok = await put_format(client, base, mode="CUSTOM", columns=parsed["columns"], terms=parsed["terms"])
    assert ok.status_code == 200


async def test_the_original_header_only_upload_still_works(client: httpx.AsyncClient, project, source: Path):
    base = await start(client, project, source)
    r = await client.post(f"{base}/mappings/target-format/parse", files={"file": ("cols.csv", b"UMR,Premium Due\n", "text/csv")}, headers=auth(TOKEN))
    assert r.status_code == 200 and r.json()["data"]["columns"] == ["UMR", "Premium Due"]
