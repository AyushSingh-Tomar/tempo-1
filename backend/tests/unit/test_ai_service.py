"""The AI layer must never raise into the workflow: every failure is a typed outcome with a reason."""

from __future__ import annotations

import io
import json
import socket
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from bordereaux.ai import service as ai
from bordereaux.ai.service import LLMService, OpenAICompatibleProvider, extract_json
from bordereaux.config import Settings
from bordereaux.core.exceptions import LLMError


def _settings(**kw: Any) -> Settings:
    base = dict(_env_file=None, llm_enabled=True, llm_provider="dial", llm_model="m", llm_api_key="k", llm_timeout_seconds=5)
    base.update(kw)
    return Settings(**base)


def _http_error(code: int, body: str = "") -> HTTPError:
    return HTTPError("http://x", code, "err", {}, io.BytesIO(body.encode()))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "text, expected",
    [
        ('{"a": 1}', {"a": 1}),
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('Sure! Here you go:\n{"a": {"b": "x}y"}} thanks', {"a": {"b": "x}y"}}),
        ("[1, 2]", [1, 2]),
    ],
)
def test_extract_json_tolerates_fences_and_prose(text: str, expected: Any) -> None:
    assert extract_json(text) == expected


def test_extract_json_rejects_text_without_json() -> None:
    with pytest.raises(ValueError):
        extract_json("no json here")


@pytest.mark.parametrize(
    "exc, status",
    [
        (_http_error(429, "rate limit"), "rate_limited"),
        (_http_error(401, "bad key"), "auth_error"),
        (_http_error(403, ""), "auth_error"),
        (_http_error(404, ""), "invalid_request"),
        (_http_error(400, ""), "invalid_request"),
        (_http_error(504, ""), "timeout"),
        (_http_error(503, ""), "unavailable"),
        (socket.timeout("timed out"), "timeout"),
        (TimeoutError(), "timeout"),
        (URLError(socket.timeout("t")), "timeout"),
        (URLError("dns failure"), "unavailable"),
        (ConnectionResetError(), "unavailable"),
    ],
)
async def test_transport_failures_become_typed_outcomes(monkeypatch: pytest.MonkeyPatch, exc: Exception, status: str) -> None:
    def boom(*_a: Any, **_k: Any) -> Any:
        raise exc

    monkeypatch.setattr(ai, "urlopen", boom)
    outcome = await LLMService(settings=_settings()).ask_json("hi")
    assert outcome.status == status
    assert not outcome.ok
    assert outcome.message  # always a human-readable reason for the UI


async def test_provider_that_hangs_is_cut_off_by_the_time_budget() -> None:
    import asyncio

    class Hangs:
        async def complete(self, prompt: str, **_: Any) -> str:
            await asyncio.sleep(30)
            return "{}"

    service = LLMService(provider=Hangs(), settings=_settings())  # type: ignore[arg-type]
    started = asyncio.get_running_loop().time()
    outcome = await service.ask_json("hi", timeout_seconds=0.1)
    assert outcome.status == "timeout"
    assert asyncio.get_running_loop().time() - started < 6


async def test_non_json_reply_is_bad_response_not_an_exception() -> None:
    class Chatty:
        async def complete(self, prompt: str, **_: Any) -> str:
            return "I think the answer is yes."

    outcome = await LLMService(provider=Chatty(), settings=_settings()).ask_json("hi")  # type: ignore[arg-type]
    assert outcome.status == "bad_response"


async def test_unexpected_provider_exception_is_contained() -> None:
    class Broken:
        async def complete(self, prompt: str, **_: Any) -> str:
            raise RuntimeError("kaboom with a secret key=abc")

    outcome = await LLMService(provider=Broken(), settings=_settings()).ask_json("hi")  # type: ignore[arg-type]
    assert outcome.status == "error"
    assert "abc" not in outcome.message  # provider internals are not echoed to the UI


async def test_success_parses_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class Resp:
        status = 200

        def __enter__(self) -> "Resp":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

        def read(self) -> bytes:
            content = '```json\n{"decisions": []}\n```'
            return json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]}).encode()

    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float = 0) -> Resp:
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data)
        captured["timeout"] = timeout
        return Resp()

    monkeypatch.setattr(ai, "urlopen", fake_urlopen)
    outcome = await LLMService(settings=_settings(llm_base_url="https://proxy.example", llm_reasoning_effort="low")).ask_json("hi")
    assert outcome.ok and outcome.data == {"decisions": []}
    assert captured["url"].startswith("https://proxy.example/openai/deployments/m/chat/completions?api-version=")
    assert captured["headers"]["Api-key"] == "k"
    assert captured["payload"]["reasoning_effort"] == "low"
    assert captured["timeout"] == 5


async def test_empty_answer_from_exhausted_token_budget_is_explained() -> None:
    with pytest.raises(LLMError) as exc:
        OpenAICompatibleProvider._extract_text({"choices": [{"message": {"content": ""}, "finish_reason": "length"}]})
    assert "LLM_MAX_TOKENS" in exc.value.message


async def test_disabled_and_missing_key_explain_themselves() -> None:
    off = await LLMService(settings=Settings(_env_file=None)).ask_json("hi")
    assert off.status == "disabled" and "LLM_ENABLED" in off.message
    status = LLMService(settings=_settings(llm_api_key=None, llm_model=None)).status()
    assert status["available"] is False and "API key" in status["reason"]
    assert LLMService(settings=_settings()).status()["available"] is True
