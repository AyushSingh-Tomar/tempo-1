from __future__ import annotations

from typing import Any

from bordereaux.ai.service import LLMService
from bordereaux.config import Settings


class RecordingProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def complete(self, prompt: str, **_: Any) -> str:
        self.calls.append({"prompt": prompt})
        return '{"ok": true, "answer": "looks good"}'

    async def is_available(self) -> bool:
        return True


def test_llm_default_is_disabled() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_enabled is False
    assert settings.llm_provider == "disabled"
    assert settings.llm_api_key is None


def test_llm_service_noop_skips_without_configuration() -> None:
    service = LLMService(settings=Settings(_env_file=None))
    assert service.is_available() is False
    result = service.answer(question="classify this variance", context={"run_id": "123"})
    assert result["status"] == "disabled"
    assert "configure" in result["message"].lower()


def test_llm_service_includes_full_context_before_calling_provider() -> None:
    provider = RecordingProvider()
    settings = Settings(
        _env_file=None,
        llm_enabled=True,
        llm_provider="custom",
        llm_model="demo-model",
    )
    service = LLMService(provider=provider, settings=settings)

    result = service.answer(
        question="Should this mapping be approved?",
        context={"run_id": "r-1", "schema": {"fields": ["claim_no", "gross_amount"]}, "candidates": [{"source": "gross"}]},
    )

    assert result["status"] == "ok"
    assert provider.calls
    prompt = provider.calls[0]["prompt"]
    assert "run_id" in prompt and "Should this mapping be approved?" in prompt
    assert "gross_amount" in prompt and "candidates" in prompt
