"""The platform-wide directory of saved final formats, through the real HTTP API, and
using one as a run's target format."""

from __future__ import annotations

from pathlib import Path

import httpx
import openpyxl
import pytest
from sqlalchemy import select

from bordereaux.models import AuditEvent
from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

ANALYST = "dev-analyst1-analyst"
OWNER = "dev-owner1-project_owner"
VIEWER = "dev-viewer1-viewer"
REVIEWER = "dev-reviewer1-reviewer"
URL = "/api/v1/format-templates"

LLOYDS = {
    "name": "Lloyd's Standard",
    "columns": [
        {"name": "UMR", "terms": []},
        {"name": "Premium Due", "terms": ["GWP", "Prime Brute"]},
    ],
}


async def create(client: httpx.AsyncClient, body: dict = LLOYDS, token: str = ANALYST) -> dict:
    r = await client.post(URL, json=body, headers=auth(token))
    assert r.status_code == 201, r.text
    return r.json()["data"]


# --- the directory -------------------------------------------------------------------


async def test_add_list_open_change_and_remove_a_format(client: httpx.AsyncClient, db_session):
    t = await create(client)
    assert (t["name"], t["column_count"], t["term_count"]) == ("Lloyd's Standard", 2, 2)
    assert t["columns"][1] == {"name": "Premium Due", "terms": ["GWP", "Prime Brute"]}

    other = await create(client, {"name": "ACORD", "columns": [{"name": "Policy"}]})
    listing = (await client.get(URL, headers=auth(VIEWER))).json()["data"]
    assert [x["name"] for x in listing] == ["ACORD", "Lloyd's Standard"]  # alphabetical, readable by every role
    assert (await client.get(f"{URL}/{t['id']}", headers=auth(VIEWER))).json()["data"]["columns"] == t["columns"]

    # Change everything in one save: rename the format, rename/add/remove columns, change terms.
    changed = {
        "name": "Lloyds V2",
        "columns": [
            {"name": "Unique Market Ref", "terms": ["UMR", "Market Reference"]},  # renamed column, new terms
            {"name": "Premium Due", "terms": ["Prime Brute"]},  # one term removed
            {"name": "Commission", "terms": []},  # column added
        ],
    }
    r = await client.put(f"{URL}/{t['id']}", json=changed, headers=auth(ANALYST))
    assert r.status_code == 200, r.text
    got = r.json()["data"]
    assert got["name"] == "Lloyds V2" and [c["name"] for c in got["columns"]] == ["Unique Market Ref", "Premium Due", "Commission"]
    assert got["columns"][0]["terms"] == ["UMR", "Market Reference"] and got["term_count"] == 3
    assert got["updated_at"] >= t["updated_at"]

    assert (await client.delete(f"{URL}/{other['id']}", headers=auth(ANALYST))).json()["data"] == {"id": other["id"], "deleted": True}
    assert [x["name"] for x in (await client.get(URL, headers=auth(ANALYST))).json()["data"]] == ["Lloyds V2"]
    assert (await client.get(f"{URL}/{other['id']}", headers=auth(ANALYST))).status_code == 404

    events = (await db_session.execute(select(AuditEvent).where(AuditEvent.event_type.like("format_template.%")))).scalars().all()
    assert sorted(e.event_type for e in events) == [
        "format_template.created", "format_template.created", "format_template.deleted", "format_template.updated",
    ]
    updated = next(e for e in events if e.event_type == "format_template.updated")
    assert updated.before_state["name"] == "Lloyd's Standard" and updated.after_state["name"] == "Lloyds V2"
    assert all(e.actor_id is not None for e in events)


async def test_names_are_unique_ignoring_case_and_punctuation(client: httpx.AsyncClient):
    a = await create(client)
    for clash in ("lloyds standard", "LLOYD'S  STANDARD", "Lloyds-Standard"):
        r = await client.post(URL, json={**LLOYDS, "name": clash}, headers=auth(ANALYST))
        assert r.status_code == 409 and r.json()["error"]["code"] == "FORMAT_NAME_TAKEN"
    b = await create(client, {"name": "Other", "columns": [{"name": "X"}]})
    assert (await client.put(f"{URL}/{b['id']}", json={**LLOYDS, "name": "lloyds standard"}, headers=auth(ANALYST))).status_code == 409
    # Re-saving a format under its own name (even re-cased) is not a clash.
    assert (await client.put(f"{URL}/{a['id']}", json={**LLOYDS, "name": "LLOYD'S STANDARD"}, headers=auth(ANALYST))).status_code == 200


@pytest.mark.parametrize(
    "body",
    [
        {"name": "  ", "columns": [{"name": "A"}]},
        {"name": "x" * 101, "columns": [{"name": "A"}]},
        {"name": "No columns", "columns": []},
        {"name": "Blank col", "columns": [{"name": "  "}]},
        {"name": "Dup", "columns": [{"name": "Gross Premium"}, {"name": "gross  premium"}]},
        {"name": "Long term", "columns": [{"name": "A", "terms": ["x" * 201]}]},
        {"name": "Punctuation only", "columns": [{"name": "###"}]},
    ],
)
async def test_invalid_formats_are_rejected(client: httpx.AsyncClient, body: dict):
    r = await client.post(URL, json=body, headers=auth(ANALYST))
    assert r.status_code in (400, 422), (body, r.status_code, r.text)
    assert (await client.get(URL, headers=auth(ANALYST))).json()["data"] == []


async def test_duplicate_columns_are_named_in_the_error(client: httpx.AsyncClient):
    r = await client.post(URL, json={"name": "D", "columns": [{"name": "A"}, {"name": "a"}]}, headers=auth(ANALYST))
    assert r.status_code == 400 and r.json()["error"]["details"] == [{"duplicate_columns": ["a"]}]


async def test_terms_are_trimmed_deduplicated_and_blanks_dropped(client: httpx.AsyncClient):
    t = await create(client, {"name": "T", "columns": [{"name": "  Gross   Premium ", "terms": [" GWP ", "gwp", "", "  ", "Prime Brute"]}]})
    assert t["columns"] == [{"name": "Gross Premium", "terms": ["GWP", "Prime Brute"]}]


async def test_only_roles_that_can_choose_a_target_format_may_change_the_directory(client: httpx.AsyncClient):
    t = await create(client)
    for token in (VIEWER, REVIEWER):
        assert (await client.get(URL, headers=auth(token))).status_code == 200
        assert (await client.post(URL, json=LLOYDS, headers=auth(token))).status_code == 403
        assert (await client.put(f"{URL}/{t['id']}", json=LLOYDS, headers=auth(token))).status_code == 403
        assert (await client.delete(f"{URL}/{t['id']}", headers=auth(token))).status_code == 403
        assert (await client.post(f"{URL}/parse", files={"file": ("a.csv", b"A\nx", "text/csv")}, headers=auth(token))).status_code == 403
    assert (await client.post(URL, json={"name": "By owner", "columns": [{"name": "A"}]}, headers=auth(OWNER))).status_code == 201
    assert (await client.get(URL)).status_code == 401  # and it needs a login
    assert len((await client.get(URL, headers=auth(VIEWER))).json()["data"]) == 2  # nothing the viewer tried was applied


async def test_unknown_format_is_404(client: httpx.AsyncClient):
    unknown = "00000000-0000-0000-0000-000000000000"
    assert (await client.get(f"{URL}/{unknown}", headers=auth(ANALYST))).status_code == 404
    assert (await client.put(f"{URL}/{unknown}", json=LLOYDS, headers=auth(ANALYST))).status_code == 404
    assert (await client.delete(f"{URL}/{unknown}", headers=auth(ANALYST))).status_code == 404


async def test_a_format_can_be_read_from_a_csv_without_saving_anything(client: httpx.AsyncClient):
    r = await client.post(f"{URL}/parse", files={"file": ("f.csv", b"UMR,Premium Due\n,GWP\n,Prime Brute\n", "text/csv")}, headers=auth(ANALYST))
    assert r.status_code == 200 and r.json()["data"] == {
        "columns": ["UMR", "Premium Due"], "terms": {"Premium Due": ["GWP", "Prime Brute"]}, "skipped_terms": 0,
    }
    assert (await client.get(URL, headers=auth(ANALYST))).json()["data"] == []
    assert (await client.post(f"{URL}/parse", files={"file": ("f.txt", b"a", "text/plain")}, headers=auth(ANALYST))).status_code == 400


# --- using a saved format for a run --------------------------------------------------


@pytest.fixture
def source(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bordereaux"
    ws.append(["UMR", "Prime Brute", "Totally Other"])
    for i in range(1, 7):
        ws.append([f"B{i}2024XY000{i}", 1000 * i, f"x{i}"])
    path = tmp_path / "template_source.xlsx"
    wb.save(path)
    return path


async def start(client: httpx.AsyncClient, project, source: Path) -> str:
    return f"/api/v1/processing-runs/{await pipeline.upload_clean(client, project, source)}"


async def candidates(client: httpx.AsyncClient, base: str) -> dict[str, dict]:
    assert (await client.post(f"{base}/mappings/generate", headers=auth("dev-admin1-admin"))).status_code == 200
    data = (await client.get(f"{base}/mappings/candidates", headers=auth("dev-admin1-admin"))).json()["data"]
    return {c["source_column"]: c for c in data["candidates"]}


async def test_a_saved_format_drives_the_mapping_like_own_columns_with_terms(client: httpx.AsyncClient, project, source: Path):
    t = await create(client)
    base = await start(client, project, source)
    admin = auth("dev-admin1-admin")

    r = await client.put(f"{base}/mappings/target-format", json={"mode": "CUSTOM", "template_id": t["id"]}, headers=admin)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["mode"] == "CUSTOM" and data["template"]["id"] == t["id"] and data["template"]["name"] == "Lloyd's Standard"
    fields = {f["display_name"]: f for f in data["fields"]}
    assert fields["Premium Due"]["name"] == "gross_premium" and fields["Premium Due"]["user_terms"] == ["GWP", "Prime Brute"]

    mapped = await candidates(client, base)
    assert mapped["Prime Brute"]["target_field"] == "gross_premium" and float(mapped["Prime Brute"]["confidence_total"]) == 1.0
    assert mapped["UMR"]["target_field"] == "umr" and mapped["Totally Other"]["target_field"].startswith("extra_")
    assert (await client.post(f"{base}/mappings/approve-exact", headers=admin)).status_code == 200
    assert (await client.post(f"{base}/mappings/finalize", headers=admin)).status_code == 200


async def test_changing_or_deleting_a_saved_format_never_changes_a_run_that_used_it(client: httpx.AsyncClient, project, source: Path):
    t = await create(client)
    base = await start(client, project, source)
    admin = auth("dev-admin1-admin")
    await client.put(f"{base}/mappings/target-format", json={"mode": "CUSTOM", "template_id": t["id"]}, headers=admin)

    await client.put(f"{URL}/{t['id']}", json={"name": "Renamed", "columns": [{"name": "Something Else", "terms": []}]}, headers=auth(ANALYST))
    snap = (await client.get(f"{base}/mappings/target-format", headers=admin)).json()["data"]
    assert snap["template"]["name"] == "Lloyd's Standard" and [f["display_name"] for f in snap["fields"]] == ["UMR", "Premium Due"]
    assert (await candidates(client, base))["Prime Brute"]["target_field"] == "gross_premium"

    assert (await client.delete(f"{URL}/{t['id']}", headers=auth(ANALYST))).status_code == 200
    snap = (await client.get(f"{base}/mappings/target-format", headers=admin)).json()["data"]
    assert snap["template"]["name"] == "Lloyd's Standard" and len(snap["fields"]) == 2
    assert (await candidates(client, base))["Prime Brute"]["target_field"] == "gross_premium"


async def test_a_saved_format_is_exclusive_with_the_other_options(client: httpx.AsyncClient, project, source: Path):
    t = await create(client)
    base = await start(client, project, source)
    admin = auth("dev-admin1-admin")
    put = lambda body: client.put(f"{base}/mappings/target-format", json=body, headers=admin)  # noqa: E731
    assert (await put({"mode": "DEFAULT", "template_id": t["id"]})).status_code == 400
    assert (await put({"mode": "CUSTOM", "template_id": t["id"], "columns": ["UMR"]})).status_code == 400
    assert (await put({"mode": "CUSTOM", "template_id": t["id"], "terms": {"UMR": ["x"]}})).status_code == 400
    assert (await put({"mode": "CUSTOM", "template_id": "00000000-0000-0000-0000-000000000000"})).status_code == 404
    assert (await put({"mode": "CUSTOM", "template_id": "not-a-uuid"})).status_code == 400
    # Nothing was applied by any of those, and the two original options still work.
    assert (await client.get(f"{base}/mappings/target-format", headers=admin)).json()["data"]["selected"] is False
    assert (await put({"mode": "DEFAULT"})).json()["data"]["template"] is None
    custom = (await put({"mode": "CUSTOM", "columns": ["UMR", "Premium Due"], "terms": {"Premium Due": ["Prime Brute"]}})).json()["data"]
    assert custom["template"] is None and custom["mode"] == "CUSTOM"
