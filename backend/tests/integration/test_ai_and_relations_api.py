"""AI assistance + user-declared money relations through the real HTTP API, with a fake model.

The point of these tests is the contract the UI relies on:
* AI is visible: every attempt (ok / disabled / timeout / limit ...) is recorded with a reason;
* AI is optional: a failing or absent model never stops mapping, relations or the checks;
* AI is advisory: its mapping answers are validated and only ever PROPOSED, its relation
  suggestions are re-measured against the data and not saved until the user adds them;
* declared relations drive the financial checks, and findings land in the discrepancy review.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import openpyxl
import pytest

from bordereaux.ai.service import LLMService
from bordereaux.config import Settings
from bordereaux.core.exceptions import LLMError
from tests.conftest import auth
from tests.integration import _pipeline as pipeline

pytestmark = pytest.mark.integration

TOKEN = pipeline.TOKEN
HEADERS = ["UMR", "Insured", "Gross Premium", "Commission", "Net Premium", "Amount X", "Amount Y"]


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """gross - commission - tax(8%) = net, except row 4; 'Amount X' is 25% of gross (an unlabelled commission-like column)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Bordereaux"
    ws.append(HEADERS)
    for i in range(1, 9):
        gross = 1000 * i
        comm = gross * 25 // 100
        net = gross - comm
        if i == 4:
            net += 90  # the planted discrepancy
        ws.append([f"B{i}2024XY000{i}", f"Insured {i}", gross, comm, net, gross * 25 // 100, 7 * i])
    path = tmp_path / "ai_source.xlsx"
    wb.save(path)
    return path


class FakeProvider:
    def __init__(self, reply: Any = None, error: Exception | None = None) -> None:
        self.reply, self.error, self.prompts = reply, error, []

    async def complete(self, prompt: str, **_: Any) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.reply if isinstance(self.reply, str) else json.dumps(self.reply)


def use_model(monkeypatch: pytest.MonkeyPatch, provider: FakeProvider | None) -> None:
    """Route both AI call sites to a fake model (or to the disabled default when ``provider`` is None)."""
    settings = Settings(_env_file=None, llm_enabled=True, llm_provider="custom", llm_model="fake-model", llm_api_key="k")
    service = LLMService(provider=provider, settings=settings) if provider else LLMService(settings=Settings(_env_file=None))
    monkeypatch.setattr("bordereaux.mapping.service.build_llm_service", lambda *a, **k: service)
    monkeypatch.setattr("bordereaux.financial_checks.relations_service.build_llm_service", lambda *a, **k: service)
    monkeypatch.setattr("bordereaux.api.v1.routes.ai.build_llm_service", lambda *a, **k: service)


async def start(client: httpx.AsyncClient, project, source: Path) -> str:
    run_id = await pipeline.upload_clean(client, project, source)
    base = f"/api/v1/processing-runs/{run_id}"
    r = await client.put(f"{base}/mappings/target-format", json={"mode": "DEFAULT"}, headers=auth(TOKEN))
    assert r.status_code == 200, r.text
    return base


async def finish_mapping(client: httpx.AsyncClient, base: str) -> None:
    await client.post(f"{base}/mappings/approve-exact", headers=auth(TOKEN))
    cands = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]["candidates"]
    for c in cands:
        if c["status"] == "PROPOSED":
            r = await client.post(f"/api/v1/mappings/{c['id']}/approve", headers=auth(TOKEN))
            assert r.status_code in (200, 409), r.text
    r = await client.post(f"{base}/mappings/finalize", headers=auth(TOKEN))
    assert r.status_code == 200, r.text


async def enter_treaty(client: httpx.AsyncClient, base: str) -> None:
    body = {"commission_pct": "0.25", "tax_pct": "0.08", "cession_pct": "0.5", "settlement_currency": "USD", "fx_rates": []}
    r = await client.post(f"{base}/treaty-figures", json=body, headers=auth(TOKEN))
    assert r.status_code == 201, r.text


async def activity(client: httpx.AsyncClient, base: str) -> list[dict[str, Any]]:
    return (await client.get(f"{base}/ai/activity", headers=auth(TOKEN))).json()["data"]["interactions"]


# ------------------------------------------------------------------ AI status + activity


async def test_ai_status_and_disabled_activity_are_visible(client, project, source, monkeypatch) -> None:
    use_model(monkeypatch, None)
    status = (await client.get("/api/v1/ai/status", headers=auth(TOKEN))).json()["data"]
    assert status["available"] is False and "LLM_ENABLED" in status["reason"]

    base = await start(client, project, source)
    gen = await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))
    assert gen.status_code == 200
    ai = gen.json()["data"]["ai"]
    assert ai["status"] == "disabled" and ai["message"]
    assert [i["status"] for i in await activity(client, base)] == ["disabled"]


async def test_user_can_skip_ai_for_the_mapping_run(client, project, source, monkeypatch) -> None:
    provider = FakeProvider({"decisions": []})
    use_model(monkeypatch, provider)
    base = await start(client, project, source)
    gen = await client.post(f"{base}/mappings/generate", params={"use_ai": "false"}, headers=auth(TOKEN))
    assert gen.json()["data"]["ai"]["status"] == "skipped"
    assert provider.prompts == []  # nothing was sent to the model


# ------------------------------------------------------------------ mapping AI


async def test_mapping_ai_sends_context_and_proposes_validated_suggestions(client, project, source, monkeypatch) -> None:
    provider = FakeProvider(
        {
            "decisions": [
                {"source_column": "Amount X", "target_field": "brokerage", "confidence": 0.8, "reason": "25% of gross"},
                {"source_column": "Amount Y", "target_field": "invented_field", "confidence": 0.99, "reason": "?"},
            ]
        }
    )
    use_model(monkeypatch, provider)
    base = await start(client, project, source)
    gen = await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))
    assert gen.status_code == 200
    ai = gen.json()["data"]["ai"]
    assert ai["status"] == "ok" and ai["items_resolved"] == 1 and ai["model"] == "fake-model"

    # the prompt carried what a person would look at: the columns, samples, targets and the neighbours
    doc = json.loads(provider.prompts[0])
    sent = {c["source_column"]: c for c in doc["columns_to_resolve"]}
    assert {"Amount X", "Amount Y"} <= set(sent)
    assert sent["Amount X"]["sample_values"] and sent["Amount X"]["previous_column"] == "Net Premium"
    assert any(f["name"] == "brokerage" for f in doc["target_fields"])
    assert "gross_premium" in doc["already_mapped_fields"]  # exact matches are settled, not re-asked

    cands = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]["candidates"]
    suggestion = next(c for c in cands if c["source_column"] == "Amount X" and c["target_field"] == "brokerage")
    assert suggestion["status"] == "PROPOSED"  # advisory: a person still has to approve
    assert any(e["type"] == "ai_suggestion" and e["reason"] == "25% of gross" for e in suggestion["evidence"])
    # the hallucinated field never reached the candidate list
    assert not any(c["target_field"] == "invented_field" for c in cands)
    # and the column still has its safe pass-through, so nothing is lost if the suggestion is ignored
    assert any(c["source_column"] == "Amount X" and c["target_field"].startswith("extra_") for c in cands)

    r = await client.post(f"/api/v1/mappings/{suggestion['id']}/approve", headers=auth(TOKEN))
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "error, status",
    [
        (LLMError("limit", details={"kind": "rate_limited"}), "rate_limited"),
        (LLMError("slow", details={"kind": "timeout"}), "timeout"),
        (LLMError("key", details={"kind": "auth_error"}), "auth_error"),
        (RuntimeError("boom"), "error"),
    ],
)
async def test_mapping_continues_when_ai_fails_and_says_why(client, project, source, monkeypatch, error, status) -> None:
    use_model(monkeypatch, FakeProvider(error=error))
    base = await start(client, project, source)
    gen = await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))
    assert gen.status_code == 200, gen.text  # the flow is never blocked
    assert gen.json()["data"]["ai"]["status"] == status
    assert gen.json()["data"]["ai"]["message"]
    await finish_mapping(client, base)  # ... and mapping can be completed by hand


async def test_retry_ai_after_a_failure_adds_suggestions(client, project, source, monkeypatch) -> None:
    use_model(monkeypatch, FakeProvider(error=LLMError("slow", details={"kind": "timeout"})))
    base = await start(client, project, source)
    await client.post(f"{base}/mappings/generate", headers=auth(TOKEN))

    use_model(monkeypatch, FakeProvider({"decisions": [{"source_column": "Amount X", "target_field": "brokerage", "confidence": 0.7, "reason": "r"}]}))
    retry = await client.post(f"{base}/mappings/ai-assist", headers=auth(TOKEN))
    assert retry.status_code == 200 and retry.json()["data"]["status"] == "ok"
    assert [i["status"] for i in await activity(client, base)] == ["ok", "timeout"]  # newest first
    cands = (await client.get(f"{base}/mappings/candidates", headers=auth(TOKEN))).json()["data"]["candidates"]
    assert any(c["target_field"] == "brokerage" and c["status"] == "PROPOSED" for c in cands)


# ------------------------------------------------------------------ relations


async def reach_relations(client, project, source, monkeypatch, provider=None) -> str:
    use_model(monkeypatch, provider)
    base = await start(client, project, source)
    await client.post(f"{base}/mappings/generate", params={"use_ai": "false"}, headers=auth(TOKEN))
    await finish_mapping(client, base)
    await enter_treaty(client, base)
    return base


async def test_declared_relations_drive_the_checks_and_reach_the_discrepancy_review(client, project, source, monkeypatch) -> None:
    base = await reach_relations(client, project, source, monkeypatch)
    ws = (await client.get(f"{base}/money-relations", headers=auth(TOKEN))).json()["data"]
    fields = {f["field"] for f in ws["fields"]}
    assert {"gross_premium", "commission", "net_premium", "extra_amount_x"} <= fields
    assert ws["editable"] and ws["relations"] == []

    # a relation on an unlabelled column - impossible with the old hard-coded rules
    r = await client.post(
        f"{base}/money-relations",
        json={"target_field": "net_premium", "terms": [{"field": "gross_premium", "sign": 1}, {"field": "commission", "sign": -1}]},
        headers=auth(TOKEN),
    )
    assert r.status_code == 201, r.text
    created = r.json()["data"]
    assert created["origin"] == "USER" and created["expression"] == "net_premium = gross_premium - commission"
    assert created["label"] == "Net Premium (100%) = Gross Premium (100%) - Coverholder Comm Amt"
    dup = await client.post(
        f"{base}/money-relations",
        json={"target_field": "net_premium", "terms": [{"field": "commission", "sign": -1}, {"field": "gross_premium", "sign": 1}]},
        headers=auth(TOKEN),
    )
    assert dup.status_code == 400  # same relation, different order

    r = await client.post(
        f"{base}/money-relations",
        json={"target_field": "extra_amount_x", "terms": [{"field": "gross_premium", "sign": 1, "factors": ["commission_pct"]}]},
        headers=auth(TOKEN),
    )
    assert r.status_code == 201, r.text

    checks = await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    assert checks.status_code == 200, checks.text
    results = checks.json()["data"]["relation_results"]
    assert [x["check_id"] for x in results] == ["REL-1", "REL-2"]
    assert results[0]["rows_evaluated"] == 8 and results[0]["rows_failed"] == 1
    assert results[1]["rows_failed"] == 0

    d = (await client.get(f"{base}/discrepancies", headers=auth(TOKEN))).json()["data"]
    findings = [f for f in d["discrepancies"] if f["check_id"].startswith("REL-")]
    assert [(f["check_id"], f["affected_row_number"], f["affected_field"]) for f in findings] == [("REL-1", 5, "net_premium")]  # sheet row 5 = data row 4
    assert Decimal(findings[0]["variance"]) == Decimal("90")
    assert findings[0]["evidence"]["relation_origin"] == "USER"
    assert not any(f["check_id"].startswith("MCR-A") for f in d["discrepancies"])  # declared set replaces the hard-coded identities
    assert len(d["relations"]) == 2  # the declared relations are echoed to the review screen
    assert next(r for r in d["relations"] if r["id"] == created["id"])["last_rows_failed"] == 1


async def test_relations_are_locked_once_checks_have_run(client, project, source, monkeypatch) -> None:
    base = await reach_relations(client, project, source, monkeypatch)
    assert (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).status_code == 200
    r = await client.post(
        f"{base}/money-relations",
        json={"target_field": "net_premium", "terms": [{"field": "gross_premium", "sign": 1}]},
        headers=auth(TOKEN),
    )
    assert r.status_code == 409


async def test_invalid_relations_are_rejected_with_a_reason(client, project, source, monkeypatch) -> None:
    base = await reach_relations(client, project, source, monkeypatch)
    for body in (
        {"target_field": "nope", "terms": [{"field": "gross_premium", "sign": 1}]},
        {"target_field": "net_premium", "terms": [{"field": "gross_premium", "sign": 3}]},
        {"target_field": "net_premium", "terms": [{"field": "gross_premium", "sign": 1, "factors": ["os.system"]}]},
        {"target_field": "net_premium", "terms": [{"field": "net_premium", "sign": 1}]},
    ):
        r = await client.post(f"{base}/money-relations", json=body, headers=auth(TOKEN))
        assert r.status_code == 400, (body, r.text)


async def test_standard_relations_are_deterministic_and_checks_match_declared_set(client, project, source, monkeypatch) -> None:
    base = await reach_relations(client, project, source, monkeypatch)
    std = (await client.post(f"{base}/money-relations/standard", headers=auth(TOKEN))).json()["data"]
    assert std["added"] >= 2
    again = (await client.post(f"{base}/money-relations/standard", headers=auth(TOKEN))).json()["data"]
    assert again["added"] == 0  # idempotent
    labels = " | ".join(r["label"] for r in std["relations"])
    assert "Net Premium (100%)" in labels and "commission_pct" in labels
    assert all(r["origin"] == "STANDARD" for r in std["relations"])
    checks = (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).json()["data"]
    assert len(checks["relation_results"]) == std["added"]
    assert any(x["rows_failed"] > 0 for x in checks["relation_results"])


async def test_without_declared_relations_the_builtin_checks_still_run(client, project, source, monkeypatch) -> None:
    base = await reach_relations(client, project, source, monkeypatch)
    checks = (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).json()["data"]
    assert checks["relation_results"] == []


async def test_ai_relation_suggestions_are_remeasured_and_not_saved(client, project, source, monkeypatch) -> None:
    reply = {
        "relations": [
            {
                "label": "Amount X is commission",
                "target_field": "extra_amount_x",
                "terms": [{"field": "gross_premium", "sign": 1, "factors": ["commission_pct"]}],
                "rationale": "25% of gross on every row",
                "confidence": 0.9,
            },
            {  # nonsense the data does not support -> discarded by the agreement check
                "label": "bogus",
                "target_field": "extra_amount_y",
                "terms": [{"field": "gross_premium", "sign": 1, "factors": ["tax_pct"]}],
                "rationale": "guess",
                "confidence": 0.9,
            },
            {"label": "invented column", "target_field": "ghost", "terms": [{"field": "gross_premium", "sign": 1}]},
        ]
    }
    provider = FakeProvider(reply)
    base = await reach_relations(client, project, source, monkeypatch, provider)
    res = (await client.post(f"{base}/money-relations/ai-suggest", headers=auth(TOKEN))).json()["data"]
    assert res["status"] == "ok" and res["interaction"]["purpose"] == "MONEY_RELATIONS"
    assert len(res["suggestions"]) == 1
    s = res["suggestions"][0]
    assert s["target_field"] == "extra_amount_x" and Decimal(s["agreement"]) == 1 and s["rows_evaluated"] == 8
    assert "discarded" in res["message"]

    # the model saw the column names, treaty figures and real rows
    doc = json.loads(provider.prompts[0])
    assert {"gross_premium", "extra_amount_x"} <= {f["field"] for f in doc["numeric_fields"]}
    assert doc["treaty_figures"]["commission_pct"] == "0.25"
    assert doc["sample_rows"] and doc["sample_rows"][0]["gross_premium"] == "1000"

    # nothing is saved until the user adds it
    assert (await client.get(f"{base}/money-relations", headers=auth(TOKEN))).json()["data"]["relations"] == []
    add = await client.post(
        f"{base}/money-relations",
        json={"label": s["label"], "target_field": s["target_field"], "terms": s["terms"], "origin": "AI_SUGGESTED", "rationale": s["rationale"]},
        headers=auth(TOKEN),
    )
    assert add.status_code == 201 and add.json()["data"]["origin"] == "AI_SUGGESTED"
    checks = (await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))).json()["data"]
    assert checks["relation_results"][0]["origin"] == "AI_SUGGESTED"


@pytest.mark.parametrize(
    "provider, status",
    [
        (None, "disabled"),
        (FakeProvider(error=LLMError("slow", details={"kind": "timeout"})), "timeout"),
        (FakeProvider(error=LLMError("limit", details={"kind": "rate_limited"})), "rate_limited"),
        (FakeProvider("not json at all"), "bad_response"),
    ],
)
async def test_manual_relations_and_checks_work_when_ai_is_unavailable(client, project, source, monkeypatch, provider, status) -> None:
    base = await reach_relations(client, project, source, monkeypatch, provider)
    res = await client.post(f"{base}/money-relations/ai-suggest", headers=auth(TOKEN))
    assert res.status_code == 200  # an AI problem is reported in the body, never as an HTTP error
    data = res.json()["data"]
    assert data["status"] == status and data["message"] and data["suggestions"] == []

    r = await client.post(
        f"{base}/money-relations",
        json={"target_field": "net_premium", "terms": [{"field": "gross_premium", "sign": 1}, {"field": "commission", "sign": -1}]},
        headers=auth(TOKEN),
    )
    assert r.status_code == 201
    checks = await client.post(f"{base}/financial-checks/run", headers=auth(TOKEN))
    assert checks.status_code == 200 and checks.json()["data"]["relation_results"][0]["rows_failed"] == 1
    assert (await client.post(f"{base}/discrepancies/proceed", headers=auth(TOKEN))).status_code == 200
