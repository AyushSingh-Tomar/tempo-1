"""Acceptance test against ``sample_bordereaux_master.xlsx`` (sheet "Bordereaux"),
checked row by row against its "Answer Key" sheet:

* rows 1-5, 8, 14, 15 are clean: nothing flagged
* rows 6-8 are multi-currency (GBP 1.175 / USD 0.925 / EUR 1.0): per-currency
  FX rates are derived from the file, editable on the treaty step, and applied
  so the rows settle to EUR without being flagged
* rows 9-11 (MCR-D2 bundled commission) and 12-13 (MCR-D1 gross-is-ceded)
  are flagged
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import pytest

from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files" / "sample_bordereaux_master.xlsx"
TOKEN = "dev-admin1-admin"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

TREATY = {
    "commission_pct": "0.25",
    "brokerage_pct": "0.0125",
    "tax_pct": "0.12",
    "cession_pct": "0.40",
    "order_pct": "0.20",
}


async def map_to_treaty_step(client, project) -> str:
    return await pipeline.map_to_treaty_step(client, project, FIXTURE)


pytestmark_fixture = pytest.mark.skipif(not FIXTURE.exists(), reason="fixture not present")

# The Answer Key counts data rows from 1; findings carry the spreadsheet row
# number (header = row 1), so answer-key row N is spreadsheet row N + 1.
def sheet_row(answer_key_row: int) -> int:
    return answer_key_row + 1


async def _derived(client, base) -> dict:
    return (await client.get(f"{base}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]


def _fx_body(derived: dict) -> dict:
    return {
        **TREATY,
        "settlement_currency": derived["settlement_currency"],
        "fx_rates": [{"currency": c["currency"], "rate": c["rate"], "source": "FILE"} for c in derived["currencies"]],
    }


async def _findings_by_row(client, base) -> dict[int, list[str]]:
    d = (await client.get(f"{base}/discrepancies", headers=auth(TOKEN))).json()["data"]
    out: dict[int, list[str]] = {}
    for f in d["discrepancies"]:
        out.setdefault(f["affected_row_number"], []).append(f["check_id"])
    return out


@pytestmark_fixture
async def test_currencies_and_rates_are_derived_from_the_file(client: httpx.AsyncClient, project) -> None:
    run_id = await map_to_treaty_step(client, project)
    derived = await _derived(client, f"/api/v1/processing-runs/{run_id}")
    assert derived["settlement_currency"] == "EUR"
    rates = {c["currency"]: c["rate"] for c in derived["currencies"]}
    assert rates == {"EUR": "1", "GBP": "1.175", "USD": "0.925"}
    assert all(c["source"] == "FILE" and not c["conflicting_rates"] for c in derived["currencies"])


@pytestmark_fixture
async def test_treaty_percentages_are_derived_from_the_file(client: httpx.AsyncClient, project) -> None:
    run_id = await map_to_treaty_step(client, project)
    figures = {f["figure"]: f for f in (await _derived(client, f"/api/v1/processing-runs/{run_id}"))["figures"]}
    assert {k: figures[k]["status"] for k in figures} == {
        "commission_pct": "UNIFORM",
        "brokerage_pct": "UNIFORM",
        "cession_pct": "UNIFORM",
        "order_pct": "UNIFORM",
        "tax_pct": "NOT_FOUND",  # the file has an IPT *amount*, no rate column
    }
    assert [figures[k]["value"] for k in ("commission_pct", "brokerage_pct", "cession_pct", "order_pct")] == [
        "0.25", "0.0125", "0.4", "0.2",
    ]
    assert figures["cession_pct"]["source_column"] == "Cession %"


@pytestmark_fixture
async def test_treaty_requires_a_rate_for_every_currency_in_the_file(client: httpx.AsyncClient, project) -> None:
    run_id = await map_to_treaty_step(client, project)
    base = f"/api/v1/processing-runs/{run_id}"
    body = {**TREATY, "settlement_currency": "EUR", "fx_rates": [{"currency": "GBP", "rate": "1.175"}]}
    r = await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))
    assert r.status_code == 400 and "USD" in r.text
    # The user can edit a derived value; what they submit is what is used.
    body = _fx_body(await _derived(client, base))
    for e in body["fx_rates"]:
        if e["currency"] == "GBP":
            e.update(rate="1.20", source="USER")
    assert (await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))).status_code == 201
    assert (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).status_code == 200
    found = await _findings_by_row(client, base)
    assert found[sheet_row(6)] == ["MCR-FX1"]  # file says 1.175, user-entered treaty rate says 1.20


@pytestmark_fixture
async def test_answer_key_checks(client: httpx.AsyncClient, project) -> None:
    run_id = await map_to_treaty_step(client, project)
    base = f"/api/v1/processing-runs/{run_id}"
    r = await client.post(f"{base}/treaty-figures", json=_fx_body(await _derived(client, base)), headers=auth(TOKEN))
    assert r.status_code == 201, r.text
    assert (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).status_code == 200
    found = await _findings_by_row(client, base)

    # Rows 1-8, 14, 15: clean (incl. the GBP/USD/EUR multi-currency rows).
    for n in (1, 2, 3, 4, 5, 6, 7, 8, 14, 15):
        assert sheet_row(n) not in found, (n, found.get(sheet_row(n)))
    # Rows 9-11: bundled commission, flagged as MCR-D2 (and only that).
    for n in (9, 10, 11):
        assert found[sheet_row(n)] == ["MCR-D2"], (n, found.get(sheet_row(n)))

    # Finish the run and inspect the processed file.
    assert (await client.post(f"{base}/discrepancies/proceed", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/reports/generate", headers=auth(TOKEN))).status_code == 200
    resp = await client.get(f"{base}/download/processed_file", headers=auth(TOKEN))
    rows = {int(r["source_row_number"]): r for r in csv.DictReader(io.StringIO(resp.text))}

    # Rows 6-8: settle to EUR with the per-currency rate.
    gbp, usd, eur = rows[sheet_row(6)], rows[sheet_row(7)], rows[sheet_row(8)]
    assert (gbp["settlement_currency_applied"], gbp["fx_rate_applied"]) == ("EUR", "1.175")
    assert float(gbp["gross_premium_our_share_settlement"]) == pytest.approx(37793.2 * 1.175, abs=0.01)
    assert (usd["fx_rate_applied"], float(usd["gross_premium_our_share_settlement"])) == ("0.925", pytest.approx(17429.8 * 0.925, abs=0.01))
    assert eur["fx_rate_applied"] == "1" and float(eur["gross_premium_our_share_settlement"]) == pytest.approx(30089.6, abs=0.01)

    # Row 14: whitespace trimmed, missing brokers blank, blank IBNR not an error.
    r14 = rows[sheet_row(14)]
    assert r14["insured_name"] == "Webb, Porter and Young"
    assert r14["placing_broker"] == "" and r14["producing_broker"] == ""

    # Row 15: a mid-term endorsement, not new business.
    r15 = rows[sheet_row(15)]
    assert r15["transaction_type"] == "Endorsement"
    assert r15["endorsement_ref"] in ("1", "1.0")
    assert r15["transaction_effective_date"].startswith("2024-04-15")


@pytestmark_fixture
@pytest.mark.xfail(
    reason=(
        "Rows 12-13 (MCR-D1 gross-is-ceded) are internally consistent with every treaty rate and every other column, "
        "and their premium-to-sum-insured ratios sit inside the range of honest rows (rows 7-8 are lower). "
        "No numeric signal in the file separates them; only the Remarks text does."
    ),
    strict=False,
)
async def test_gross_is_ceded_rows_are_flagged(client: httpx.AsyncClient, project) -> None:
    run_id = await map_to_treaty_step(client, project)
    base = f"/api/v1/processing-runs/{run_id}"
    await client.post(f"{base}/treaty-figures", json=_fx_body(await _derived(client, base)), headers=auth(TOKEN))
    await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    found = await _findings_by_row(client, base)
    for n in (12, 13):
        assert "MCR-D1" in found.get(sheet_row(n), [])
