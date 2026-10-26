"""A user's own API key: stored encrypted, verified before saving, never echoed, and really used for AI calls."""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import text

from bordereaux.ai import credentials
from bordereaux.ai.service import AIOutcome, LLMService
from bordereaux.config import Settings
from tests.conftest import auth
from tests.integration.test_ai_and_relations_api import FakeProvider, source, start, use_model  # noqa: F401

pytestmark = pytest.mark.integration

ME = "dev-user-a-analyst"
OTHER = "dev-user-b-analyst"
KEY = "sk-live-ABCDEFGH-1234567890-wxyz"


def ok_outcome() -> AIOutcome:
    return AIOutcome("ok", "AI answered.", {"ok": True}, model="m", provider="dial", latency_ms=1200)


def bad_outcome(status: str = "auth_error") -> AIOutcome:
    return AIOutcome(status, f"reason: {status}", model="m", provider="dial", latency_ms=300)


def patch_check(monkeypatch: pytest.MonkeyPatch, outcome: AIOutcome) -> list[str]:
    seen: list[str] = []

    async def fake(key: str) -> AIOutcome:
        seen.append(key)
        return outcome

    monkeypatch.setattr("bordereaux.api.v1.routes.ai.check_key", fake)
    return seen


async def put_key(client, token: str = ME, key: str = KEY, **extra: Any):
    return await client.put("/api/v1/me/ai-key", json={"api_key": key, **extra}, headers=auth(token))


async def test_valid_key_is_verified_stored_encrypted_and_never_returned(client, db_session, monkeypatch) -> None:
    seen = patch_check(monkeypatch, ok_outcome())
    r = await put_key(client)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert seen == [KEY] and data["saved"] is True and data["test"]["status"] == "ok"
    assert data["key_source"] == "user" and data["user_key"] == {
        "configured": True, "hint": "wxyz", "validated_at": data["user_key"]["validated_at"],
    }
    assert data["user_key"]["validated_at"]

    # nothing the API says contains the key
    for path in ("/api/v1/me/ai-key", "/api/v1/ai/status"):
        body = (await client.get(path, headers=auth(ME))).text
        assert KEY not in body and "ABCDEFGH" not in body

    # at rest it is ciphertext that decrypts back with the master key
    stored = (await db_session.execute(text("SELECT encrypted_key, key_hint FROM user_ai_credentials"))).one()
    assert KEY not in stored[0] and stored[1] == "wxyz"
    assert credentials.decrypt_key(stored[0]) == KEY

    # and it is not in the audit trail
    audit = (await db_session.execute(text("SELECT event_type, after_state FROM audit_events WHERE event_type LIKE 'ai_key.%'"))).all()
    assert [a[0] for a in audit] == ["ai_key.set"] and KEY not in json.dumps([str(a[1]) for a in audit])


async def test_key_the_provider_rejects_is_not_saved(client, monkeypatch) -> None:
    patch_check(monkeypatch, bad_outcome("auth_error"))
    data = (await put_key(client)).json()["data"]
    assert data["saved"] is False and data["test"]["status"] == "auth_error" and data["test"]["message"]
    assert data["user_key"]["configured"] is False


async def test_unreachable_provider_can_still_save_untested_on_request(client, monkeypatch) -> None:
    patch_check(monkeypatch, bad_outcome("unavailable"))
    assert (await put_key(client)).json()["data"]["saved"] is False
    data = (await put_key(client, skip_test=True)).json()["data"]
    assert data["saved"] is True and data["user_key"]["configured"] and data["user_key"]["validated_at"] is None


@pytest.mark.parametrize("bad", ["short", "has spaces in it 12345", "wide−char-12345678", ""])
async def test_malformed_keys_are_rejected_before_any_call(client, monkeypatch, bad) -> None:
    seen = patch_check(monkeypatch, ok_outcome())
    r = await put_key(client, key=bad)
    assert r.status_code in (400, 422) and seen == []


async def test_pasted_quotes_and_whitespace_are_cleaned(client, monkeypatch) -> None:
    seen = patch_check(monkeypatch, ok_outcome())
    assert (await put_key(client, key=f'  "{KEY}"\n')).json()["data"]["saved"] is True
    assert seen == [KEY]


async def test_keys_are_per_user_and_removable(client, monkeypatch) -> None:
    patch_check(monkeypatch, ok_outcome())
    await put_key(client)
    assert (await client.get("/api/v1/me/ai-key", headers=auth(OTHER))).json()["data"]["user_key"]["configured"] is False
    assert (await client.get("/api/v1/me/ai-key", headers=auth(ME))).json()["data"]["user_key"]["hint"] == "wxyz"
    removed = (await client.delete("/api/v1/me/ai-key", headers=auth(ME))).json()["data"]
    assert removed["removed"] is True and removed["user_key"]["configured"] is False and removed["key_source"] == "none"
    assert (await client.delete("/api/v1/me/ai-key", headers=auth(ME))).json()["data"]["removed"] is False


async def test_retest_of_stored_key(client, monkeypatch) -> None:
    patch_check(monkeypatch, ok_outcome())
    assert (await client.post("/api/v1/me/ai-key/test", headers=auth(ME))).status_code == 404
    await put_key(client)
    patch_check(monkeypatch, bad_outcome("rate_limited"))
    data = (await client.post("/api/v1/me/ai-key/test", headers=auth(ME))).json()["data"]
    assert data["test"]["status"] == "rate_limited" and data["user_key"]["configured"] is True


async def test_unauthenticated_requests_are_refused(client) -> None:
    assert (await client.get("/api/v1/me/ai-key")).status_code == 401
    assert (await client.put("/api/v1/me/ai-key", json={"api_key": KEY})).status_code == 401


# ------------------------------------------------------------------ the key is really used


def test_user_key_reuses_the_apps_provider_config_and_replaces_only_the_secret() -> None:
    base = Settings(_env_file=None, llm_enabled=True, llm_provider="dial", llm_model="my-model", llm_api_key="server-key",
                    llm_base_url="https://proxy.example", llm_api_version="v9")
    s = credentials.settings_with_key(KEY, base)
    assert (s.llm_api_key, s.llm_provider, s.llm_model, s.llm_base_url, s.llm_api_version) == (KEY, "dial", "my-model", "https://proxy.example", "v9")
    # server has AI switched off: the user's key still works, against the app's default provider
    off = credentials.settings_with_key(KEY, Settings(_env_file=None))
    assert off.llm_enabled and off.llm_provider == "dial" and off.llm_api_key == KEY and off.llm_model


async def test_the_users_key_is_what_goes_over_the_wire(monkeypatch) -> None:
    from bordereaux.ai import service as ai

    captured: dict[str, Any] = {}

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return None
        def read(self): return json.dumps({"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}).encode()

    def fake_urlopen(request, timeout=0):
        captured["key"] = dict(request.header_items()).get("Api-key")
        captured["url"] = request.full_url
        return Resp()

    monkeypatch.setattr(ai, "urlopen", fake_urlopen)
    outcome = await credentials.check_key(KEY)
    assert outcome.ok and captured["key"] == KEY and "/openai/deployments/" in captured["url"]


async def test_mapping_and_relations_use_the_users_key_when_the_server_has_none(client, project, source, monkeypatch) -> None:  # noqa: F811
    use_model(monkeypatch, None)  # server: AI disabled
    patch_check(monkeypatch, ok_outcome())
    # pipeline helpers authenticate as admin1; give that user a key
    await client.put("/api/v1/me/ai-key", json={"api_key": KEY}, headers=auth("dev-admin1-admin"))
    assert (await client.get("/api/v1/ai/status", headers=auth("dev-admin1-admin"))).json()["data"]["available"] is True

    provider = FakeProvider({"decisions": [{"source_column": "Amount X", "target_field": "brokerage", "confidence": 0.8, "reason": "r"}]})
    used: list[str] = []

    def fake_service(key: str) -> LLMService:
        used.append(key)
        return LLMService(provider=provider, settings=Settings(_env_file=None, llm_enabled=True, llm_provider="custom", llm_model="m", llm_api_key=key))

    monkeypatch.setattr("bordereaux.ai.credentials.service_for_key", fake_service)
    base = await start(client, project, source)
    gen = await client.post(f"{base}/mappings/generate", headers=auth("dev-admin1-admin"))
    assert gen.json()["data"]["ai"]["status"] == "ok"
    assert used == [KEY] and provider.prompts

    # a different user without a key still gets the server default (disabled)
    other = await client.get("/api/v1/ai/status", headers=auth(OTHER))
    assert other.json()["data"]["available"] is False and other.json()["data"]["key_source"] == "none"
