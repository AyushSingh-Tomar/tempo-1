"""Every provided workbook, end to end through the real HTTP API, checked against
its own "Answer Key" sheet.

Each workbook carries three sheets the tests read directly:

* "Bordereaux" - uploaded and processed (upload -> validate -> clean ->
  acknowledge -> target format -> generate -> review -> finalize);
* "Treaty Figures" - the figures entered at the treaty step (percentages and
  per-currency FX rates);
* "Answer Key" - what the system should do with each row.

``test_pipeline_matches_answer_key`` is generic and runs for all 13 files.
Where the app deliberately does not (or cannot) reproduce the key, the row is
listed in ``KNOWN_GAPS`` with the reason; the test fails if a gap closes or a
new one opens, so the list cannot drift. The remaining tests pin the specific
behaviours the key describes (mapping, cleaning, structure, FX, traps, totals).
"""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path

import httpx
import openpyxl
import pytest

from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[3] / "Initial provided Info" / "Test_files"
WORKBOOKS = sorted(FIXTURES.glob("*.xlsx")) if FIXTURES.exists() else []
TOKEN = pipeline.TOKEN
XLSX = pipeline.XLSX


def path_of(name: str) -> Path:
    return FIXTURES / f"{name}.xlsx"


needs_fixtures = pytest.mark.skipif(not WORKBOOKS, reason="fixtures not present")

# Answer-key rows count data rows from 1; findings carry the spreadsheet row
# (header = row 1, but title rows above the header shift it further).
def sheet_row(key_row: int, offset: int = 1) -> int:
    return key_row + offset


# --------------------------------------------------------------------------
# Reading the workbook's own sheets
# --------------------------------------------------------------------------


def read_treaty(path: Path) -> tuple[dict[str, str], dict[str, str]]:
    """("Treaty Figures" sheet) -> treaty body fields, and the per-currency FX rates."""
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    values = {r[0]: r[1] for r in wb["Treaty Figures"].iter_rows(values_only=True) if r and r[0]}

    def pct(label: str) -> str:
        text = str(values[label]).strip()
        return str(float(text.strip("%")) / 100) if text.endswith("%") else text

    treaty = {
        "commission_pct": pct("Commission %"),
        "brokerage_pct": pct("Brokerage %"),
        "tax_pct": pct("Tax / IPT %"),
        "cession_pct": pct("Cession %"),
        "order_pct": pct("Order %"),
    }
    fx = dict(re.findall(r"([A-Z]{3})\s+([0-9.]+)", str(values.get("FX Rates", ""))))
    return treaty, fx


def read_answer_key(path: Path) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    rows = list(wb["Answer Key"].iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if r[0] is not None]


def bordereaux_sheet(path: Path) -> str:
    wb = openpyxl.load_workbook(path, read_only=True)
    return next(s for s in wb.sheetnames if s.startswith("Bordereaux"))


def read_source_rows(path: Path) -> tuple[list[str], list[tuple]]:
    """Header and data rows of the Bordereaux sheet exactly as a user would see them."""
    ws = openpyxl.load_workbook(path, data_only=True)[bordereaux_sheet(path)]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = next(i for i, r in enumerate(rows) if sum(v is not None for v in r) >= 40)
    return [str(h) for h in rows[header_idx]], rows[header_idx + 1 :]


# --------------------------------------------------------------------------
# Driving a run
# --------------------------------------------------------------------------


async def run_workbook(client: httpx.AsyncClient, project, path: Path, **treaty_extra) -> dict:
    """Upload -> ... -> treaty figures from the workbook -> financial checks ->
    proceed -> report. Returns what the assertions need."""
    run_id = await pipeline.map_to_treaty_step(client, project, path, bordereaux_sheet(path))
    base = f"/api/v1/processing-runs/{run_id}"
    treaty, file_fx = read_treaty(path)
    derived = (await client.get(f"{base}/treaty-figures/derived", headers=auth(TOKEN))).json()["data"]
    body = {
        **treaty,
        **treaty_extra,
        "settlement_currency": derived["settlement_currency"],
        "fx_rates": [
            {"currency": c["currency"], "rate": file_fx.get(c["currency"]) or c["rate"] or "1", "source": "FILE"}
            for c in derived["currencies"]
        ],
    }
    r = await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))
    assert r.status_code == 201, (path.name, r.text)
    r = await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    assert r.status_code == 200, (path.name, r.text)
    checks = r.json()["data"]
    d = (await client.get(f"{base}/discrepancies", headers=auth(TOKEN))).json()["data"]
    found: dict[int, list[str]] = {}
    for f in d["discrepancies"]:
        found.setdefault(f["affected_row_number"], []).append(f["check_id"])
    assert (await client.post(f"{base}/discrepancies/proceed", headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/reports/generate", headers=auth(TOKEN))).status_code == 200
    text = (await client.get(f"{base}/download/processed_file", headers=auth(TOKEN))).text
    processed = {int(r["source_row_number"]): r for r in csv.DictReader(io.StringIO(text))}
    mappings = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]
    return {
        "run_id": run_id,
        "base": base,
        "found": found,
        "checks": checks,
        "processed": processed,
        "approved": {m["source_column"]: m["target_field"] for m in mappings["approved_mappings"]},
    }


# --------------------------------------------------------------------------
# 1. Generic: all 13 workbooks against their Answer Key
# --------------------------------------------------------------------------

# Answer-key rows that are really the file's total rows: they are set aside, not processed.
TOTAL_ROWS_IN_KEY = {"test_mcr_04_signs_totals_ambiguity": {19, 20}}
# Rows above the header in the sheet (title block + blank lines).
HEADER_OFFSET = {"test_std_01_structural": 7}

# Where the Answer Key's expected flag is NOT what the app produces, and why.
# {answer-key row: "missing"} = the key expects a flag the app does not raise;
# {answer-key row: "extra"}   = the app flags a row the key calls clean.
KNOWN_GAPS: dict[str, dict[int, str]] = {
    # MCR-D1 gross-is-ceded: the trap rows are arithmetically perfect honest rows (every
    # identity, ratio and commission anchor holds, premium/sum-insured sits inside the range
    # of honest rows). Only the Remarks text tells them apart, so nothing numeric can flag them
    # without the optional "expected rate on sum insured" treaty input (see the realistic test).
    "sample_bordereaux_master": {12: "missing", 13: "missing"},
    "test_integration_realistic": {13: "missing"},
    "test_mcr_03_traps": {6: "missing", 7: "missing", 8: "missing", 9: "missing", 10: "missing"},
    # Rows 6/12/18 write only commission and net in (parentheses) - negative - against a
    # positive gross: mixed signs are an inconsistency under MCR-G1, so they are flagged.
    # The key only asks that cleaning turn the parentheses into negatives (tested below).
    "test_std_02_formats": {6: "extra", 12: "extra", 18: "extra"},
}


def expected_flag(name: str, entry: dict) -> bool | None:
    """Whether the key expects a finding on this row. ``None``: not a data row."""
    row = int(entry["Row #"])
    if row in TOTAL_ROWS_IN_KEY.get(name, set()):
        return None
    flag = entry.get("Expected Flag?")
    if flag is None:  # sample_bordereaux_master has no flag column: its scenarios say TRAP
        return "TRAP" in str(entry["Scenario"])
    return str(flag).startswith(("Yes", "Ambiguous"))


@needs_fixtures
@pytest.mark.parametrize("path", WORKBOOKS, ids=lambda p: p.stem)
async def test_pipeline_matches_answer_key(client: httpx.AsyncClient, project, path: Path) -> None:
    name = path.stem
    key = read_answer_key(path)
    res = await run_workbook(client, project, path)

    # Every non-total row of the key is a processed row; totals/footers never are.
    key_rows = {int(e["Row #"]) for e in key} - TOTAL_ROWS_IN_KEY.get(name, set())
    offset = HEADER_OFFSET.get(name, 1)
    assert set(res["processed"]) == {sheet_row(n, offset) for n in key_rows}, name

    mismatches: dict[int, str] = {}
    for entry in key:
        flag = expected_flag(name, entry)
        if flag is None:
            continue
        n = int(entry["Row #"])
        got = bool(res["found"].get(sheet_row(n, offset)))
        if flag and not got:
            mismatches[n] = "missing"
        elif got and not flag:
            mismatches[n] = "extra"
    assert mismatches == KNOWN_GAPS.get(name, {}), (name, res["found"])


@needs_fixtures
async def test_control_file_raises_nothing(client: httpx.AsyncClient, project) -> None:
    """The zero-issues control: no discrepancy of any kind, and nothing suggested."""
    res = await run_workbook(client, project, path_of("test_control_zero_issues"))
    assert res["found"] == {} and res["checks"]["discrepancies_found"] == 0


# --------------------------------------------------------------------------
# 2. Mapping flow (test_map_01 / 02 / 03, and the master)
# --------------------------------------------------------------------------


async def mapping_review(client: httpx.AsyncClient, project, path: Path) -> dict:
    """Run to the mapping step and capture what the reviewer sees at each stage."""
    run_id = await pipeline.upload_clean(client, project, path, bordereaux_sheet(path))
    base = f"/api/v1/processing-runs/{run_id}"
    assert (await client.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=auth(TOKEN))).status_code == 200
    assert (await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))).status_code == 200

    async def candidates() -> dict:
        return (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]

    generated = await candidates()
    r = await client.post(f"{base}/mappings/approve-exact", headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    after_exact = await candidates()
    return {"base": base, "generated": generated, "after_exact": after_exact}


def by_source(data: dict, status: str | None = None) -> dict[str, dict]:
    return {
        c["source_column"]: c
        for c in data["candidates"]
        if (status is None or c["status"] == status) and not c["target_field"].startswith("extra_")
    }


# header in the file -> canonical field it must resolve to (taken from the same column
# position in sample_bordereaux_master, whose headers are the dictionary's own terms).
FUZZY_ABBREVIATIONS = {
    "Pol Nmbr": "policy_ref",
    "Insrd Nm": "insured_name",
    "Brkr": "placing_broker",
    "Sum Insd": "sum_insured",
    "FX Rt": "fx_rate",
    "Grs Prem": "gross_premium",
    "Net Prm": "net_premium",
}
# "Incep Dt" is a dictionary alias (exact) but, like "Period From", also names inception_date:
# a duplicate-target conflict, so it needs a reviewer instead of being auto-approved.
CONFLICTING_TARGETS = {"inception_date", "class_of_business"}
SEMANTIC_SYNONYMS = {
    "Insurance Reference": "policy_ref",
    "Risk Insured": "insured_name",
    "Delegated Authority": "coverholder_name",
    "Placement Intermediary": "placing_broker",
    "Attachment Date": "inception_date",
    "Business Line": "class_of_business",
    "Total Insured Value": "sum_insured",
    "Written Premium": "gross_premium",
    "Ceding Fee": "commission",
    "Premium Net of Deductions": "net_premium",
}


@needs_fixtures
async def test_map_01_mangled_headers_are_fuzzy_matched_for_review(client: httpx.AsyncClient, project) -> None:
    review = await mapping_review(client, project, path_of("test_map_01_exact_fuzzy"))
    generated = by_source(review["generated"])
    for header, target in FUZZY_ABBREVIATIONS.items():
        cand = generated[header]
        assert cand["target_field"] == target, header
        stage = next(e["stage"] for e in cand["evidence"] if e["type"] == "alias_match")
        assert stage == "FUZZY" and 0.80 <= float(cand["confidence_total"]) < 1.0, (header, cand["confidence_total"])
        assert cand["auto_approve_eligible"] is False, header  # a fuzzy match always needs a human
    # "Approve all 100% matches" must leave every fuzzy match for the reviewer...
    still_open = by_source(review["after_exact"], "PROPOSED")
    assert {"Pol Nmbr", "Grs Prem", "Insrd Nm", "Brkr", "Sum Insd", "FX Rt", "Net Prm"} <= set(still_open)
    assert generated["Incep Dt"]["target_field"] == "inception_date" and "Incep Dt" in still_open
    # ...and take the exact dictionary terms.
    approved = {m["source_column"]: m["target_field"] for m in review["after_exact"]["approved_mappings"]}
    assert approved["UMR"] == "umr" and approved["Brokerage"] == "brokerage" and approved["IPT"] == "tax"
    assert "Grs Prem" not in approved


@needs_fixtures
async def test_map_01_fuzzy_mapped_values_reach_the_processed_file(client: httpx.AsyncClient, project) -> None:
    path = path_of("test_map_01_exact_fuzzy")
    res = await run_workbook(client, project, path)
    assert {res["approved"][h] for h in FUZZY_ABBREVIATIONS} == set(FUZZY_ABBREVIATIONS.values())
    header, data = read_source_rows(path)
    col = {h: i for i, h in enumerate(header)}
    for i, row in enumerate(data):
        out = res["processed"][i + 2]
        assert out["policy_ref"] == row[col["Pol Nmbr"]]
        assert float(out["gross_premium"]) == pytest.approx(float(row[col["Grs Prem"]]))
        assert float(out["sum_insured"]) == pytest.approx(float(row[col["Sum Insd"]]))
    # With gross, commission, tax, net all mapped the arithmetic is actually checked (honest file: clean).
    assert res["found"] == {}


@needs_fixtures
async def test_map_02_semantic_synonyms_resolve_by_meaning(client: httpx.AsyncClient, project) -> None:
    review = await mapping_review(client, project, path_of("test_map_02_semantic"))
    approved = {m["source_column"]: m["target_field"] for m in review["after_exact"]["approved_mappings"]}
    generated = {c["source_column"]: c for c in review["generated"]["candidates"]}
    for header, target in SEMANTIC_SYNONYMS.items():
        cand = generated[header]
        assert cand["target_field"] == target and any(e["stage"] == "EXACT" for e in cand["evidence"] if e["type"] == "alias_match")
        if target in CONFLICTING_TARGETS:
            assert header not in approved  # waits for the reviewer (see CONFLICTING_TARGETS)
        else:  # a dictionary synonym is a deterministic 100% match, approved in bulk
            assert float(cand["confidence_total"]) == 1.0 and approved[header] == target, header


@needs_fixtures
async def test_map_02_semantic_headers_feed_the_financial_checks(client: httpx.AsyncClient, project) -> None:
    res = await run_workbook(client, project, path_of("test_map_02_semantic"))
    assert res["found"] == {}
    assert res["checks"]["rows_checked"] == 18
    first = res["processed"][2]
    assert float(first["gross_premium"]) > 0 and float(first["commission"]) > 0 and float(first["net_premium"]) > 0


@needs_fixtures
async def test_map_03_ambiguous_amount_columns_are_inferred_from_arithmetic(client: httpx.AsyncClient, project) -> None:
    review = await mapping_review(client, project, path_of("test_map_03_arithmetic_passthrough"))
    # Mapping never invents a meaning for "Amount n": all six pass through untouched.
    approved = {m["source_column"]: m["target_field"] for m in review["after_exact"]["approved_mappings"]}
    assert {approved[f"Amount {i}"] for i in range(1, 7)} == {f"extra_amount_{i}" for i in range(1, 7)}
    assert not any(c["target_field"] == "unresolved_money" for c in review["generated"]["candidates"])

    res = await run_workbook(client, project, path_of("test_map_03_arithmetic_passthrough"))
    suggested = {s["source_column"]: s for s in res["checks"]["column_role_suggestions"]}
    # master positions: Amount 1..6 = Gross, Commission, Net, Final Net, IPT, Brokerage
    expected = {
        "Amount 1": "gross_premium",
        "Amount 2": "commission",
        "Amount 3": "net_premium",
        "Amount 4": "final_net_premium",
        "Amount 5": "tax",
        "Amount 6": "brokerage",
    }
    assert {k: suggested[k]["suggested_field"] for k in expected} == expected
    assert not any(suggested[k]["is_ambiguous"] for k in expected)
    # ...as suggestions for the reviewer: nothing was re-mapped, nothing flagged.
    assert res["found"] == {}


# --------------------------------------------------------------------------
# 3. Standardisation: cleaning, structure, sheets (test_std_01 / 02 / 03)
# --------------------------------------------------------------------------


@needs_fixtures
async def test_std_01_title_block_blank_rows_total_and_footer_are_not_data(client: httpx.AsyncClient, project) -> None:
    path = path_of("test_std_01_structural")
    res = await run_workbook(client, project, path)
    rows = res["processed"]
    # 7 title/blank lines, header on row 7, 18 policies on rows 8-25; "TOTAL" (27) and the footer (29) are out.
    assert sorted(rows) == list(range(8, 26))
    assert all(r["policy_ref"].startswith("POL-") for r in rows.values())
    # The total row is cross-checked against the data instead (MCR-F1 per column, MCR-F2 identity).
    totals = res["checks"]["total_checks"]
    assert {(t["rule_id"], t["row_number"]) for t in totals} == {("MCR-F1", 27), ("MCR-F2", 27)}
    assert all(t["holds"] for t in totals) and res["found"] == {}


@needs_fixtures
async def test_std_02_formats_are_parsed_to_canonical_values(client: httpx.AsyncClient, project) -> None:
    res = await run_workbook(client, project, path_of("test_std_02_formats"))
    rows = res["processed"]

    def row(key_row: int) -> dict:
        return rows[sheet_row(key_row)]

    # DD/MM/YYYY text
    assert [row(k)["inception_date"][:10] for k in (1, 7, 13)] == ["2024-09-27", "2024-08-27", "2024-04-15"]
    assert [row(k)["inception_date"][:10] for k in (2, 8, 14)] == ["2024-07-07", "2024-08-19", "2024-03-11"]  # D-Mon-YY
    assert [float(row(k)["gross_premium"]) for k in (3, 9, 15)] == [330034.0, 116365.0, 98868.0]  # "€ 330,034.00"
    assert [float(row(k)["gross_premium"]) for k in (4, 10, 16)] == [391707.0, 94659.0, 354046.0]  # "391707,0"
    assert [row(k)["insured_name"] for k in (5, 11, 17)] == ["Clarke Ltd", "Jordan-Fox", "Fisher-Dunn"]
    for k in (6, 12, 18):  # "(38320.0)" -> -38320.0
        assert float(row(k)["commission"]) < 0 and float(row(k)["net_premium"]) < 0
    assert float(row(6)["commission"]) == -38320.0 and float(row(6)["net_premium"]) == -134120.0
    # No row in the file is clean-by-accident: the rows the key calls clean are not flagged...
    for k in range(1, 19):
        if k not in (6, 12, 18):
            assert sheet_row(k) not in res["found"], (k, res["found"].get(sheet_row(k)))
    # ...and the three mixed-sign rows are flagged for sign consistency (MCR-G1), not for parsing.
    for k in (6, 12, 18):
        assert "MCR-G1" in res["found"][sheet_row(k)]


@needs_fixtures
async def test_std_03_multisheet_workbook_requires_a_sheet_and_processes_the_bordereaux(
    client: httpx.AsyncClient, project
) -> None:
    path = path_of("test_std_03_multisheet")
    url = f"/api/v1/projects/{project.id}/processing-runs"
    r = await client.post(url, files={"file": (path.name, path.read_bytes(), XLSX)}, headers=auth(TOKEN))
    assert r.status_code == 201
    data = r.json()["data"]
    # The system never guesses between sheets: it lists them and waits for the user.
    assert data["requires_sheet_selection"] is True
    assert data["available_sheets"] == ["Cover", "Instructions", "Bordereaux Q1 2024", "Treaty Figures", "Answer Key"]
    base = f"/api/v1/processing-runs/{data['run']['id']}"
    r = await client.post(f"{base}/validate", headers=auth(TOKEN))
    assert r.status_code >= 400 and "Bordereaux Q1 2024" in r.text

    res = await run_workbook(client, project, path)  # the user picks "Bordereaux Q1 2024"
    assert sorted(res["processed"]) == list(range(2, 20))
    assert res["found"] == {}


# --------------------------------------------------------------------------
# 4. Money-column resolution: core deduction, basis, traps, signs/totals
# --------------------------------------------------------------------------


@needs_fixtures
async def test_mcr_01_deduction_and_ratio_violations(client: httpx.AsyncClient, project) -> None:
    found = (await run_workbook(client, project, path_of("test_mcr_01_core_deduction")))["found"]
    for k in (*range(1, 9), 17, 18, 19, 20):  # honest rows, brokerage rows, zero-gross row, baseline
        assert sheet_row(k) not in found, (k, found.get(sheet_row(k)))
    for k in range(9, 13):  # MCR-A1 violation: net premium inconsistent (A4/A5 share Net)
        assert found[sheet_row(k)] == ["MCR-A1", "MCR-A4", "MCR-A5"], k
    for k in range(13, 17):  # MCR-B1 violation: commission != gross x comm%
        assert found[sheet_row(k)] == ["MCR-B1"], k


@needs_fixtures
async def test_mcr_02_basis_alignment_fx_and_our_share(client: httpx.AsyncClient, project) -> None:
    res = await run_workbook(client, project, path_of("test_mcr_02_basis_alignment"))
    for k in range(1, 18):  # our-share scaling, multi-currency, cession x order chain: all clean
        assert sheet_row(k) not in res["found"], (k, res["found"].get(sheet_row(k)))
    for k in (18, 19, 20):  # MCR-D5 trap: "100%" column holds our-share values -> flagged
        assert res["found"][sheet_row(k)], k
    rates = {"GBP": 1.175, "USD": 0.925, "EUR": 1.0}
    currency = {11: "GBP", 12: "USD", 13: "GBP", 14: "USD", 1: "EUR"}
    for k, ccy in currency.items():
        out = res["processed"][sheet_row(k)]
        assert out["settlement_currency_applied"] == "EUR" and float(out["fx_rate_applied"]) == rates[ccy], k
        assert float(out["gross_premium_our_share_settlement"]) == pytest.approx(
            float(out["gross_premium_our_share"]) * rates[ccy], abs=0.01
        ), k


@needs_fixtures
async def test_mcr_03_bundled_commission_and_net_traps(client: httpx.AsyncClient, project) -> None:
    found = (await run_workbook(client, project, path_of("test_mcr_03_traps")))["found"]
    for k in range(1, 6):
        assert sheet_row(k) not in found, (k, found.get(sheet_row(k)))
    for k in range(11, 16):  # MCR-D2: reported as the bundling trap (instead of a pile of B1/B2 failures)
        assert found[sheet_row(k)] == ["MCR-D2"], k
    for k in (16, 17, 18):  # MCR-D3: "Net Premium" is net-of-commission only -> the deduction identity fails
        assert "MCR-A1" in found[sheet_row(k)], k
    for k in (19, 20):  # MCR-D4: no deduction identity fits -> never asserted as fine, routed to review
        assert "MCR-A1" in found[sheet_row(k)], k


@needs_fixtures
async def test_mcr_04_signs_zero_gross_and_total_rows(client: httpx.AsyncClient, project) -> None:
    res = await run_workbook(client, project, path_of("test_mcr_04_signs_totals_ambiguity"))
    # Cancellation rows (all money negative) and the zero-gross row are not errors.
    assert res["found"] == {}
    # The 18 policies are processed; SUBTOTAL (sheet row 20) and GRAND TOTAL (21) are not policies.
    assert sorted(res["processed"]) == list(range(2, 20))
    for k in (16, 17):
        r = res["processed"][sheet_row(k)]
        assert all(float(r[f]) < 0 for f in ("gross_premium", "commission", "tax", "net_premium"))
    # MCR-F1: the subtotal is the sum of data rows 1-15. MCR-F2: the identity holds at aggregate.
    totals = res["checks"]["total_checks"]
    assert totals and all(t["holds"] for t in totals)
    assert {("MCR-F1", 20), ("MCR-F2", 20), ("MCR-F1", 21), ("MCR-F2", 21)} <= {(t["rule_id"], t["row_number"]) for t in totals}


@needs_fixtures
async def test_integration_realistic_endorsement_cancellation_cleaning(client: httpx.AsyncClient, project) -> None:
    res = await run_workbook(client, project, path_of("test_integration_realistic"))
    assert set(res["found"]) == {sheet_row(14), sheet_row(15)}
    assert res["found"][sheet_row(14)] == ["MCR-D2"]
    assert res["found"][sheet_row(15)] == ["MCR-A1", "MCR-A4", "MCR-A5"]
    r19, r20 = res["processed"][sheet_row(19)], res["processed"][sheet_row(20)]
    assert r19["transaction_type"] == "Endorsement" and r19["transaction_effective_date"].startswith("2024-07-08")
    assert all(float(r20[f]) < 0 for f in ("gross_premium", "commission", "brokerage", "tax", "net_premium", "final_net_premium"))
