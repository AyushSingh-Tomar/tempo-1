"""``test_integration_realistic.xlsx`` (sheet "Bordereaux") against its "Answer Key"."""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import pytest

from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files" / "test_integration_realistic.xlsx"
TOKEN = pipeline.TOKEN
TREATY = {  # the workbook's own "Treaty Figures" sheet
    "commission_pct": "0.22",
    "brokerage_pct": "0.015",
    "tax_pct": "0.11",
    "cession_pct": "0.45",
    "order_pct": "0.20",
}
needs_fixture = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture not present")


def sheet_row(answer_key_row: int) -> int:
    """Answer-key rows count data rows from 1; findings use spreadsheet rows (header = 1)."""
    return answer_key_row + 1


async def run_to_checks(
    client: httpx.AsyncClient, project, extra: dict | None = None
) -> tuple[str, dict[int, list[str]]]:
    run_id = await pipeline.map_to_treaty_step(client, project, FIXTURE)
    base = f"/api/v1/processing-runs/{run_id}"
    derived = (await client.get(f"{base}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]
    body = {
        **TREATY,
        **(extra or {}),
        "settlement_currency": derived["settlement_currency"],
        "fx_rates": [{"currency": c["currency"], "rate": c["rate"], "source": "FILE"} for c in derived["currencies"]],
    }
    r = await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))
    assert r.status_code == 201, r.text
    r = await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    d = (await client.get(f"{base}/discrepancies", headers=auth(TOKEN))).json()["data"]
    found: dict[int, list[str]] = {}
    for f in d["discrepancies"]:
        found.setdefault(f["affected_row_number"], []).append(f["check_id"])
    return run_id, found


@needs_fixture
async def test_answer_key_flags(client: httpx.AsyncClient, project) -> None:
    _, found = await run_to_checks(client, project)
    # Rows 1-12, 16-20: nothing flagged - honest rows, GBP rows, cleaning-only rows,
    # the endorsement and the cancellation (negative money, ratios hold).
    for n in [*range(1, 13), 16, 17, 18, 19, 20]:
        assert sheet_row(n) not in found, (n, found.get(sheet_row(n)))
    # Row 14: commission bundles brokerage -> MCR-D2 (instead of a pile of B1/B2 failures).
    assert found[sheet_row(14)] == ["MCR-D2"]
    # Row 15: isolated Net Premium error -> A1 (+ the identities that share Net).
    assert found[sheet_row(15)] == ["MCR-A1", "MCR-A4", "MCR-A5"]
    assert set(found) == {sheet_row(14), sheet_row(15)}


@needs_fixture
async def test_gross_is_ceded_row_flagged_when_expected_si_rate_is_given(client: httpx.AsyncClient, project) -> None:
    """Row 13's premium is exactly sum insured x 5% x cession 45%. Nothing in
    the file alone says 5% is the right rate for that sum insured, so the
    check needs the technical rate as an (optional) treaty input."""
    _, found = await run_to_checks(client, project, {"expected_si_rate": "0.05"})
    assert found[sheet_row(13)] == ["MCR-D1"]
    assert set(found) == {sheet_row(13), sheet_row(14), sheet_row(15)}


@needs_fixture
async def test_treaty_inputs_derived_from_file(client: httpx.AsyncClient, project) -> None:
    run_id = await pipeline.map_to_treaty_step(client, project, FIXTURE)
    d = (await client.get(f"/api/v1/processing-runs/{run_id}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]
    assert {c["currency"]: c["rate"] for c in d["currencies"]} == {"EUR": "1", "GBP": "1.175"}
    figs = {f["figure"]: f for f in d["figures"]}
    assert [figs[k]["value"] for k in ("commission_pct", "brokerage_pct", "cession_pct", "order_pct")] == [
        "0.22", "0.015", "0.45", "0.2",
    ]
    assert figs["commission_pct"]["source_column"] == "Comm %" and figs["tax_pct"]["status"] == "NOT_FOUND"


@needs_fixture
async def test_output_file_cleaning_endorsement_cancellation_and_fx(client: httpx.AsyncClient, project) -> None:
    run_id, _ = await run_to_checks(client, project)
    base = f"/api/v1/processing-runs/{run_id}"
    assert (await client.post(f"{base}/discrepancies/proceed", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/reports/generate", headers=auth(TOKEN))).status_code == 200
    text = (await client.get(f"{base}/download/processed_file", headers=auth(TOKEN))).text
    rows = {int(r["source_row_number"]): r for r in csv.DictReader(io.StringIO(text))}

    # Rows 16-18: trimmed, case-standardised names; upper-case country codes.
    expected = {16: ("Ellis-Patel", "MW"), 17: ("Newman, Palmer and Webster", "VA"), 18: ("Griffin-Hussain", "DM")}
    for n, (name, country) in expected.items():
        assert (rows[sheet_row(n)]["insured_name"], rows[sheet_row(n)]["insured_country"]) == (name, country)
    # Mixed-case names are left alone.
    assert rows[sheet_row(19)]["insured_name"] == "Brooks, Ellis and O'Brien"

    # Row 19: mid-term endorsement, effective date populated.
    r19 = rows[sheet_row(19)]
    assert r19["transaction_type"] == "Endorsement" and r19["endorsement_ref"] in ("1", "1.0")
    assert r19["transaction_effective_date"].startswith("2024-07-08")

    # Row 20: cancellation keeps negative money across the board.
    r20 = rows[sheet_row(20)]
    for f in ("gross_premium", "commission", "brokerage", "tax", "net_premium", "final_net_premium"):
        assert float(r20[f]) < 0, f

    # Rows 11-12: GBP settles to EUR at 1.175; EUR rows at 1.
    for n in (11, 12):
        r = rows[sheet_row(n)]
        assert (r["settlement_currency_applied"], r["fx_rate_applied"]) == ("EUR", "1.175")
        assert float(r["gross_premium_our_share_settlement"]) == pytest.approx(float(r["gross_premium_our_share"]) * 1.175, abs=0.01)
    assert rows[sheet_row(1)]["fx_rate_applied"] == "1"
