"""Reconciliation workspace against the real provided workbooks: combine
``sample_bordereaux_master`` and ``test_integration_realistic`` (both sheet
"Bordereaux") into one final bordereaux, derive a subledger from the data,
plant one discrepancy and check the rule finds exactly that."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import openpyxl
import pytest

from tests.conftest import auth

pytestmark = pytest.mark.integration
FIXTURES = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files"
FILES = [FIXTURES / "sample_bordereaux_master.xlsx", FIXTURES / "test_integration_realistic.xlsx"]
TOKEN = "dev-admin1-admin"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _ledger_csv() -> tuple[bytes, str]:
    """Subledger posting = gross premium + IPT per UMR; the first UMR is booked 5.00 short."""
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Contract Ref", "GL Date", "Posted Amount"])
    first = None
    for path in FILES:
        ws = openpyxl.load_workbook(path, data_only=True)["Bordereaux"]
        rows = list(ws.iter_rows(values_only=True))
        ix = {h: i for i, h in enumerate(rows[0])}
        for r in rows[1:]:
            amount = float(r[ix["Gross Premium"]]) + float(r[ix["IPT"]])
            if first is None:
                first, amount = r[ix["UMR"]], amount - 5
            w.writerow([r[ix["UMR"]], r[ix["Booking Date"]].date().isoformat(), f"{amount:.2f}"])
    return out.getvalue().encode("utf-8"), first


@pytest.mark.skipif(not all(f.exists() for f in FILES), reason="fixtures not present")
async def test_real_workbooks_combine_and_reconcile(client: httpx.AsyncClient, project) -> None:
    b = (await client.post(f"/api/v1/projects/{project.id}/recon/datasets", json={"kind": "BORDEREAUX", "name": "Both"}, headers=auth(TOKEN))).json()["data"]["id"]
    r = await client.post(
        f"/api/v1/recon/datasets/{b}/files", files=[("files", (f.name, f.read_bytes(), XLSX)) for f in FILES], headers=auth(TOKEN)
    )
    files = r.json()["data"]["files"]
    assert all(f["needs_sheet_choice"] and f["encoding_info"]["method"] == "NOT_APPLICABLE" for f in files)
    for f in files:
        r = await client.patch(f"/api/v1/recon/datasets/{b}/files/{f['id']}", json={"selected_sheets": ["Bordereaux"]}, headers=auth(TOKEN))
        assert r.status_code == 200
    summary = (await client.post(f"/api/v1/recon/datasets/{b}/schema-summary", json={}, headers=auth(TOKEN))).json()["data"]["summary"]
    assert len(summary["common_columns"]) >= 50 and summary["unique_columns"] == [] and not summary["type_conflicts"]

    r = await client.post(f"/api/v1/recon/datasets/{b}/finalize", json={"period_column": "booking_date"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    rep = r.json()["data"]["report"]
    assert rep["row_count"] == 15 + 20 and rep["years"] == [2024]
    assert {q["quarter"] for q in rep["quarters"]} <= {"Q1", "Q2", "Q3", "Q4"} and rep["rows_without_period"] == 0
    assert "inception_date" in rep["date_columns"] and not rep["unparsed_dates"]

    ledger, first_umr = _ledger_csv()
    s = (await client.post(f"/api/v1/projects/{project.id}/recon/datasets", json={"kind": "SUBLEDGER", "name": "GL"}, headers=auth(TOKEN))).json()["data"]["id"]
    await client.post(f"/api/v1/recon/datasets/{s}/files", files=[("files", ("gl.csv", ledger, "text/csv"))], headers=auth(TOKEN))
    r = await client.post(f"/api/v1/recon/datasets/{s}/finalize", json={"period_column": "gl_date"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text

    body = {
        "bordereaux_dataset_id": b,
        "subledger_dataset_id": s,
        "rules": [{"name": "Premium + IPT", "expression": "bordereaux.gross_premium + bordereaux.ipt = subledger.posted_amount"}],
        "group_by": [{"bordereaux": "umr", "subledger": "contract_ref", "label": "UMR"}],
    }
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=body, headers=auth(TOKEN))
    assert r.status_code == 201, r.text
    rule = (await client.get(f"/api/v1/recon/runs/{r.json()['data']['id']}", headers=auth(TOKEN))).json()["data"]["result"]["rules"][0]
    bad = [g for g in rule["groups"] if g["status"] != "MATCHED"]
    assert [(g["labels"][0], g["variance"]) for g in bad] == [(first_umr, "5.00")]
    assert rule["counts"]["MATCHED"] == 34

    # restricting to the other half of the data (by source file) excludes the planted gap
    body["filters"] = [{"side": "bordereaux", "column": "_source_file", "op": "in", "values": ["test_integration_realistic.xlsx"]}]
    body["group_by"] = [{"bordereaux": "umr", "subledger": "contract_ref", "label": "UMR"}]
    body["filters"].append({"side": "subledger", "column": "contract_ref", "op": "not_in", "values": [first_umr]})
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=body, headers=auth(TOKEN))
    res = (await client.get(f"/api/v1/recon/runs/{r.json()['data']['id']}", headers=auth(TOKEN))).json()["data"]
    assert res["result"]["rows_in_scope"]["bordereaux"] == 20
    assert {g["status"] for g in res["result"]["rules"][0]["groups"]} == {"MATCHED", "ONLY_IN_SUBLEDGER"}


@pytest.mark.skipif(not (FIXTURES / "test_integration_realistic.xlsx").exists(), reason="fixture not present")
async def test_processed_file_flows_into_reconciliation(client: httpx.AsyncClient, project) -> None:
    from tests.integration import _pipeline as pipeline
    from tests.integration.test_realistic_answer_key import FIXTURE, TREATY

    run_id = await pipeline.map_to_treaty_step(client, project, FIXTURE)
    base = f"/api/v1/processing-runs/{run_id}"
    # not available before the run has produced its processed file
    r = await client.post(f"{base}/reconciliation/bordereaux", headers=auth(TOKEN))
    assert r.status_code == 409 and r.json()["error"]["code"] == "RUN_NOT_COMPLETED"

    derived = (await client.get(f"{base}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]
    body = {**TREATY, "settlement_currency": derived["settlement_currency"],
            "fx_rates": [{"currency": c["currency"], "rate": c["rate"]} for c in derived["currencies"]]}
    assert (await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))).status_code == 201
    assert (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/discrepancies/proceed", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/reports/generate", headers=auth(TOKEN))).status_code == 200

    r = await client.post(f"{base}/reconciliation/bordereaux", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    ds = r.json()["data"]
    assert ds["created"] and ds["status"] == "FINAL" and ds["kind"] == "BORDEREAUX" and ds["row_count"] == 20
    assert ds["project_id"] == str(project.id) and ds["config"]["source_run_id"] == run_id
    assert ds["report"]["period_column"] == "booking_date" and ds["report"]["years"] == [2024]
    # idempotent
    again = (await client.post(f"{base}/reconciliation/bordereaux", headers=auth(TOKEN))).json()["data"]
    assert again["id"] == ds["id"] and again["created"] is False

    # ...and it works as the bordereaux side of a reconciliation with a user-supplied subledger
    rows = (await client.get(f"/api/v1/recon/datasets/{ds['id']}/preview", params={"limit": 200}, headers=auth(TOKEN))).json()["data"]["rows"]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Contract", "Amount"])
    for row in rows:
        w.writerow([row["umr"], row["gross_premium"]])
    s = (await client.post(f"/api/v1/projects/{project.id}/recon/datasets", json={"kind": "SUBLEDGER", "name": "GL"}, headers=auth(TOKEN))).json()["data"]["id"]
    await client.post(f"/api/v1/recon/datasets/{s}/files", files=[("files", ("gl.csv", out.getvalue().encode(), "text/csv"))], headers=auth(TOKEN))
    assert (await client.post(f"/api/v1/recon/datasets/{s}/finalize", json={}, headers=auth(TOKEN))).status_code == 200
    run = {"bordereaux_dataset_id": ds["id"], "subledger_dataset_id": s,
           "rules": [{"expression": "bordereaux.gross_premium = subledger.amount"}],
           "group_by": [{"bordereaux": "umr", "subledger": "contract"}]}
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=run, headers=auth(TOKEN))
    assert r.status_code == 201 and r.json()["data"]["status"] == "RECONCILED"
