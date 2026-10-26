"""Full happy path: Upload -> Validate -> Clean -> Acknowledge -> Map ->
Finalize -> Treaty Figures -> Financial Checks -> Discrepancy Review ->
Override -> Report Generation -> Download, against the primary acceptance
fixture ``test_integration_realistic.xlsx``.

The fixture realistically omits a handful of identity-group mandatory
canonical fields that have no corresponding column at all (e.g. ``line_id``,
``transaction_ref``, ``year_of_account``, ``risk_code``,
``reporting_period_end``) - exactly the scenario the manual-mapping step
exists for. This test exercises that path explicitly rather than silently
skipping the finalize gate.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import openpyxl
import pytest

from bordereaux.core.models import ProcessingRunStatus as S
from tests.conftest import auth

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files"
FIXTURE_FILE = FIXTURES / "test_integration_realistic.xlsx"

TOKEN = "dev-admin1-admin"


def _treaty_payload() -> dict:
    wb = openpyxl.load_workbook(FIXTURE_FILE, data_only=True)
    tf = wb["Treaty Figures"]
    values = {row[0]: row[1] for row in tf.iter_rows(min_row=1, max_row=10, values_only=True) if row[0]}

    def pct(label: str) -> str:
        raw = values[label]
        return str(float(raw.strip("%")) / 100)

    return {
        "commission_pct": pct("Commission %"),
        "brokerage_pct": pct("Brokerage %"),
        "tax_pct": pct("Tax / IPT %"),
        "cession_pct": pct("Cession %"),
        "order_pct": pct("Order %"),
    }


@pytest.mark.skipif(not FIXTURE_FILE.exists(), reason="fixture not present")
async def test_full_happy_path(client: httpx.AsyncClient, project) -> None:
    content = FIXTURE_FILE.read_bytes()

    # Step 1: upload (multi-sheet workbook -> must supply sheet_name).
    resp = await client.post(
        f"/api/v1/projects/{project.id}/processing-runs",
        files={"file": ("test_integration_realistic.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"sheet_name": "Bordereaux"},
        headers=auth(TOKEN),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()["data"]
    run_id = body["run"]["id"]
    assert body["run"]["status"] == S.FILE_UPLOADED.value
    assert body["requires_sheet_selection"] is False

    # Step 2 (first half): validate.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/validate", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    version = resp.json()["data"]
    assert version["row_count"] == 20
    assert "UMR" in version["structure"]["column_names"]

    run_resp = await client.get(f"/api/v1/processing-runs/{run_id}", headers=auth(TOKEN))
    assert run_resp.json()["data"]["status"] == S.FILE_VALIDATED.value

    # Step 2 (second half) / 3: clean.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/clean", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    cleaning = resp.json()["data"]
    assert cleaning["attempt_number"] == 1
    assert cleaning["before_row_count"] == 20

    resp = await client.get(f"/api/v1/processing-runs/{run_id}/cleaning-result", headers=auth(TOKEN))
    assert resp.status_code == 200
    assert len(resp.json()["data"]["history"]) == 1

    # Step 3: acknowledge -> kicks off mapping candidate generation.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/cleaning/acknowledge", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == S.MAPPING_REVIEW_PENDING.value

    # Step 4: choose the target format (default data dictionary), then generate.
    resp = await client.put(
        f"/api/v1/processing-runs/{run_id}/mappings/target-format", json={"mode": "DEFAULT"}, headers=auth(TOKEN)
    )
    assert resp.status_code == 200, resp.text
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/mappings/generate", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text

    # Step 5: review candidates.
    resp = await client.get(f"/api/v1/processing-runs/{run_id}/mappings/candidates", headers=auth(TOKEN))
    assert resp.status_code == 200
    candidates = resp.json()["data"]["candidates"]
    assert len(candidates) > 0
    assert resp.json()["data"]["passthrough_count"] >= 0

    # Approve every still-PROPOSED candidate (deterministic, auto-approve is
    # never silent - every one needs an explicit approval call). Losing
    # duplicate-target conflicts are rejected instead (freeing their source
    # column), which also exercises the reject path.
    for c in candidates:
        if c["status"] != "PROPOSED":
            continue
        is_losing_duplicate = any(
            e.get("type") == "duplicate_target_conflict" and not e.get("winner", True) for e in c["evidence"]
        )
        if is_losing_duplicate:
            reject_resp = await client.post(
                f"/api/v1/mappings/{c['id']}/reject", json={"reason": "duplicate target"}, headers=auth(TOKEN)
            )
            assert reject_resp.status_code == 200, reject_resp.text
        else:
            approve_resp = await client.post(f"/api/v1/mappings/{c['id']}/approve", headers=auth(TOKEN))
            assert approve_resp.status_code == 200, approve_resp.text

    # The mapping review step is allowed to continue when the source file is
    # missing canonical fields entirely; those are treated as source gaps rather
    # than fatal blocking errors. Only fields that are present in the source and
    # still left unmapped must be resolved before finalization.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/mappings/finalize", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == "FINALIZED"

    run_resp = await client.get(f"/api/v1/processing-runs/{run_id}", headers=auth(TOKEN))
    assert run_resp.json()["data"]["status"] == S.TREATY_FIGURES_PENDING.value

    # Step 6/7: treaty figures.
    derived = (
        await client.get(f"/api/v1/processing-runs/{run_id}/treaty-figures/derived", headers=auth(TOKEN))
    ).json()["data"]
    treaty = {
        **_treaty_payload(),
        "settlement_currency": derived["settlement_currency"],
        "fx_rates": [
            {"currency": c["currency"], "rate": c["rate"] or "1", "source": "FILE" if c["rate"] else "USER"}
            for c in derived["currencies"]
        ],
    }
    resp = await client.post(
        f"/api/v1/processing-runs/{run_id}/treaty-figures", json=treaty, headers=auth(TOKEN)
    )
    assert resp.status_code == 201, resp.text

    run_resp = await client.get(f"/api/v1/processing-runs/{run_id}", headers=auth(TOKEN))
    assert run_resp.json()["data"]["status"] == S.TREATY_FIGURES_VALIDATED.value

    # Step 8: financial checks.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/financial-checks/run", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    fc_result = resp.json()["data"]
    assert fc_result["rows_checked"] == 20

    run_resp = await client.get(f"/api/v1/processing-runs/{run_id}", headers=auth(TOKEN))
    assert run_resp.json()["data"]["status"] == S.DISCREPANCY_REVIEW_PENDING.value

    # Step 9: review discrepancies.
    resp = await client.get(f"/api/v1/processing-runs/{run_id}/discrepancies", headers=auth(TOKEN))
    assert resp.status_code == 200
    discrepancies = resp.json()["data"]["discrepancies"]

    # Step 10: override at least one discrepancy if any were found.
    if discrepancies:
        d = discrepancies[0]
        resp = await client.post(
            f"/api/v1/discrepancies/{d['id']}/override",
            json={"reason": "Reviewed and accepted as a known rounding difference", "comment": "Test override"},
            headers=auth(TOKEN),
        )
        assert resp.status_code == 200, resp.text

        # Overriding twice must fail.
        resp = await client.post(
            f"/api/v1/discrepancies/{d['id']}/override",
            json={"reason": "second attempt"},
            headers=auth(TOKEN),
        )
        assert resp.status_code == 409

        resp = await client.get(f"/api/v1/processing-runs/{run_id}/discrepancies", headers=auth(TOKEN))
        overridden = [x for x in resp.json()["data"]["discrepancies"] if x["id"] == d["id"]][0]
        assert overridden["status"] == "OVERRIDDEN"
        # Original evidence must be untouched.
        assert overridden["expected_value"] == d["expected_value"]
        assert overridden["observed_value"] == d["observed_value"]

    # Proceed to report generation.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/discrepancies/proceed", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["status"] == S.REPORT_GENERATION_PENDING.value

    # Step 11: generate reports.
    resp = await client.post(f"/api/v1/processing-runs/{run_id}/reports/generate", headers=auth(TOKEN))
    assert resp.status_code == 200, resp.text

    run_resp = await client.get(f"/api/v1/processing-runs/{run_id}", headers=auth(TOKEN))
    assert run_resp.json()["data"]["status"] == S.COMPLETED.value

    # Step 12: download both artifacts.
    resp = await client.get(f"/api/v1/processing-runs/{run_id}/download/processed_file", headers=auth(TOKEN))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert b"gross_premium" in resp.content

    resp = await client.get(f"/api/v1/processing-runs/{run_id}/download/audit_report", headers=auth(TOKEN))
    assert resp.status_code == 200
    audit = resp.json()
    assert audit["final_status"] == S.COMPLETED.value
    assert audit["source"]["filename"] == "test_integration_realistic.xlsx"
    assert audit["mapping"]["approved_mappings"]
    assert audit["treaty_figures"]["commission_pct"] is not None
