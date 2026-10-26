"""End to end: build a final bordereaux from several files (different years /
quarters / formats / encodings), a final subledger, then reconcile."""

from __future__ import annotations

import io
from pathlib import Path

import httpx
import openpyxl
import pytest

from tests.conftest import auth

pytestmark = pytest.mark.integration
TOKEN = "dev-admin1-admin"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(sheets: dict[str, list[list]]) -> bytes:
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# Q1 2024 bordereaux: CSV in Windows-1252 (note the "é" and day-first dates)
BORD_Q1 = "Treaty ID,Cédant,Booking Date,Gross Premium,Tax\nTR-1,Société A,15/01/2024,\"1,000.00\",100\nTR-2,Société B,20/02/2024,500,50\n".encode("cp1252")
# Q3 2024 + Q1 2025 in one workbook with a cover sheet, ISO-like datetimes and an extra column
import datetime as dt

BORD_XLSX = _xlsx(
    {
        "Cover": [["Quarterly bordereaux"]],
        "Q3": [["treaty_id", "cedant", "booking_date", "gross_premium", "tax", "Region"], ["TR-1", "Societe A", dt.datetime(2024, 8, 5), 300, 30, "EU"]],
        "Q1-25": [["treaty_id", "cedant", "booking_date", "gross_premium", "tax", "Region"], ["TR-1", "Societe A", dt.datetime(2025, 2, 1), 700, 70, "EU"]],
    }
)
SUB_CSV = (
    "Treaty Ref,Posting Date,Total Amount\n"
    "tr-1,2024-01-31,1100.00\n"   # Q1 24 TR-1 = 1000+100 -> matches
    "TR-2,2024-02-28,540.00\n"    # TR-2 = 550 -> variance -10
    "TR-1,2024-08-31,330.00\n"    # Q3 24 matches
    "TR-1,2025-02-28,770.00\n"    # Q1 25 matches
    "TR-9,2024-02-28,10.00\n"     # only in subledger
).encode("utf-8")


async def _dataset(client, project, kind, name) -> str:
    r = await client.post(f"/api/v1/projects/{project.id}/recon/datasets", json={"kind": kind, "name": name}, headers=auth(TOKEN))
    assert r.status_code == 201, r.text
    return r.json()["data"]["id"]


async def test_build_both_datasets_and_reconcile(client: httpx.AsyncClient, project) -> None:
    # ---- encoding options for the dropdown
    r = await client.get("/api/v1/recon/encodings", headers=auth(TOKEN))
    assert {"value": "cp1252", "label": "Windows-1252 (Western European)"} in r.json()["data"]["encodings"]

    # ---- final bordereaux from a CSV + a multi-sheet workbook
    b_id = await _dataset(client, project, "BORDEREAUX", "Final bordereaux")
    r = await client.post(
        f"/api/v1/recon/datasets/{b_id}/files",
        files=[("files", ("q1_2024.csv", BORD_Q1, "text/csv")), ("files", ("later.xlsx", BORD_XLSX, XLSX))],
        headers=auth(TOKEN),
    )
    assert r.status_code == 201, r.text
    csv_file, xlsx_file = r.json()["data"]["files"]
    # encoding was detected and double-checked against competing readings
    assert csv_file["encoding"] == "cp1252"
    info = csv_file["encoding_info"]
    assert info["method"] == "DETECTED" and info["compared"][0] == "cp1252"
    # the workbook has several sheets -> the user must choose
    assert xlsx_file["needs_sheet_choice"] and xlsx_file["sheets"] == ["Cover", "Q3", "Q1-25"]

    # finalising before choosing sheets is refused
    r = await client.post(f"/api/v1/recon/datasets/{b_id}/finalize", json={}, headers=auth(TOKEN))
    assert r.status_code == 400 and "Choose at least one sheet" in r.text

    r = await client.patch(
        f"/api/v1/recon/datasets/{b_id}/files/{xlsx_file['id']}", json={"selected_sheets": ["Q3", "Q1-25"]}, headers=auth(TOKEN)
    )
    assert r.status_code == 200 and r.json()["data"]["selected_sheets"] == ["Q3", "Q1-25"]
    # an unknown sheet is rejected
    r = await client.patch(f"/api/v1/recon/datasets/{b_id}/files/{xlsx_file['id']}", json={"selected_sheets": ["Nope"]}, headers=auth(TOKEN))
    assert r.status_code == 400

    # forcing the wrong encoding warns; the user can restrict the search instead
    r = await client.patch(f"/api/v1/recon/datasets/{b_id}/files/{csv_file['id']}", json={"encoding": "utf-8"}, headers=auth(TOKEN))
    assert r.json()["data"]["encoding_info"]["warnings"]
    r = await client.patch(
        f"/api/v1/recon/datasets/{b_id}/files/{csv_file['id']}", json={"encoding": "", "candidate_encodings": ["utf-8", "cp1252"]}, headers=auth(TOKEN)
    )
    assert r.json()["data"]["encoding"] == "cp1252"

    # ---- schema summary before combining: common / unique columns
    r = await client.post(f"/api/v1/recon/datasets/{b_id}/schema-summary", json={}, headers=auth(TOKEN))
    s = r.json()["data"]["summary"]
    assert s["common_columns"] == ["booking_date", "cedant", "gross_premium", "tax", "treaty_id"]  # "Cédant" == "cedant"
    assert s["partial_columns"] == ["region"] and s["unique_columns"] == []
    assert len(s["tables"]) == 3

    # ---- finalize: one date format, years & quarters listed
    r = await client.post(f"/api/v1/recon/datasets/{b_id}/finalize", json={"period_column": "booking_date"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    ds = r.json()["data"]
    rep = ds["report"]
    assert ds["status"] == "FINAL" and ds["row_count"] == 4
    assert rep["years"] == [2024, 2025]
    assert [q["period"] for q in rep["quarters"]] == ["2024-Q1", "2024-Q3", "2025-Q1"]
    assert rep["date_format"] == "YYYY-MM-DD" and "booking_date" in rep["date_columns"]
    prev = (await client.get(f"/api/v1/recon/datasets/{b_id}/preview", headers=auth(TOKEN))).json()["data"]
    assert sorted(r_["booking_date"] for r_ in prev["rows"]) == ["2024-01-15", "2024-02-20", "2024-08-05", "2025-02-01"]
    assert {r_["_source_file"] for r_ in prev["rows"]} == {"q1_2024.csv", "later.xlsx"}
    assert any(r_["gross_premium"] == "1000.00" for r_ in prev["rows"])
    # a final dataset is immutable
    r = await client.post(f"/api/v1/recon/datasets/{b_id}/finalize", json={}, headers=auth(TOKEN))
    assert r.status_code == 409

    # ---- final subledger (same flow, one CSV)
    s_id = await _dataset(client, project, "SUBLEDGER", "Final subledger")
    r = await client.post(f"/api/v1/recon/datasets/{s_id}/files", files=[("files", ("ledger.csv", SUB_CSV, "text/csv"))], headers=auth(TOKEN))
    assert r.status_code == 201 and not r.json()["data"]["files"][0]["needs_sheet_choice"]
    r = await client.post(f"/api/v1/recon/datasets/{s_id}/finalize", json={"period_column": "posting_date"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["report"]["years"] == [2024, 2025]

    # ---- column values for the filter pickers
    r = await client.get(f"/api/v1/recon/datasets/{b_id}/columns/_quarter/values", headers=auth(TOKEN))
    assert {v["value"] for v in r.json()["data"]["values"]} == {"Q1", "Q3"}

    # ---- rule: bordereaux.gross_premium + bordereaux.tax = subledger.total_amount, per treaty and period
    run_body = {
        "name": "Premium to ledger",
        "bordereaux_dataset_id": b_id,
        "subledger_dataset_id": s_id,
        "rules": [{"name": "Gross + tax = ledger", "expression": "bordereaux.gross_premium + bordereaux.tax = subledger.total_amount"}],
        "group_by": [
            {"bordereaux": "treaty_id", "subledger": "treaty_ref", "label": "Treaty"},
            {"bordereaux": "_period", "subledger": "_period", "label": "Period"},
        ],
        "tolerance": {"absolute": "0.01"},
    }
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=run_body, headers=auth(TOKEN))
    assert r.status_code == 201, r.text
    run_id = r.json()["data"]["id"]
    res = (await client.get(f"/api/v1/recon/runs/{run_id}", headers=auth(TOKEN))).json()["data"]
    rule = res["result"]["rules"][0]
    by = {(g["labels"][0].upper(), g["labels"][1]): g for g in rule["groups"]}
    assert by[("TR-1", "2024-Q1")]["status"] == "MATCHED"
    assert by[("TR-1", "2024-Q3")]["status"] == "MATCHED" and by[("TR-1", "2025-Q1")]["status"] == "MATCHED"
    assert by[("TR-2", "2024-Q1")]["status"] == "VARIANCE" and by[("TR-2", "2024-Q1")]["variance"] == "10.00"
    assert by[("TR-9", "2024-Q1")]["status"] == "ONLY_IN_SUBLEDGER"
    assert res["status"] == "UNRECONCILED" and rule["grain"] == ["Treaty", "Period"]

    # ---- filters: a specific treaty and year/quarter, applied to both datasets
    run_body["filters"] = [
        {"side": "bordereaux", "column": "treaty_id", "op": "in", "values": ["TR-1"]},
        {"side": "subledger", "column": "treaty_ref", "op": "in", "values": ["TR-1"]},
        {"side": "both", "column": "_year", "op": "in", "values": ["2024"]},
    ]
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=run_body, headers=auth(TOKEN))
    res = (await client.get(f"/api/v1/recon/runs/{r.json()['data']['id']}", headers=auth(TOKEN))).json()["data"]
    assert res["status"] == "RECONCILED"
    assert res["result"]["rows_in_scope"] == {"bordereaux": 2, "subledger": 2, "bordereaux_total": 4, "subledger_total": 5}

    # ---- drill down to the rows behind a variance, and export
    key = by[("TR-2", "2024-Q1")]["key"]
    r = await client.get(f"/api/v1/recon/runs/{run_id}/records", params={"rule_id": "R1", "side": "bordereaux", "key": key}, headers=auth(TOKEN))
    assert r.json()["data"]["total"] == 1 and r.json()["data"]["rows"][0]["treaty_id"] == "TR-2"
    r = await client.get(f"/api/v1/recon/runs/{run_id}/export", headers=auth(TOKEN))
    assert r.headers["content-type"].startswith("text/csv") and "ONLY_IN_SUBLEDGER" in r.text

    # ---- bad rules are explained, not crashed
    bad = {**run_body, "filters": [], "rules": [{"expression": "bordereaux.nope = subledger.total_amount"}]}
    r = await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=bad, headers=auth(TOKEN))
    assert r.status_code == 400 and "Unknown bordereaux column" in r.text
    # a dataset of the wrong kind is refused
    swapped = {**run_body, "bordereaux_dataset_id": s_id, "subledger_dataset_id": b_id}
    assert (await client.post(f"/api/v1/projects/{project.id}/recon/runs", json=swapped, headers=auth(TOKEN))).status_code == 400
    # run list
    r = await client.get(f"/api/v1/projects/{project.id}/recon/runs", headers=auth(TOKEN))
    assert len(r.json()["data"]["runs"]) == 2
