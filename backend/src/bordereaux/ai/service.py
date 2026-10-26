"""Optional LLM layer.

The platform follows the project principle of "deterministic first, AI second".
The AI layer is intentionally isolated and disabled by default so the core
workflow continues to work without any external model configuration.
"""

from __future__ import annotations

import asyncio
import json
import re
import socket
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from bordereaux.config import Settings, get_settings
from bordereaux.core.exceptions import LLMError

_DEFAULT_SYSTEM_PROMPT = (
    "You are an interpretation assistant for a reinsurance bordereaux workflow. "
    "Use only the provided evidence; never change the underlying financial state, "
    "never fabricate a mapping or a discrepancy outcome, and return a compact JSON object. "
    "Explain your reasoning briefly and keep the answer grounded in the supplied context."
)


# Outcome vocabulary shared with the UI (frontend/src/api/types.ts -> AiStatus).
AI_OK = "ok"
AI_DISABLED = "disabled"
AI_TIMEOUT = "timeout"
AI_RATE_LIMITED = "rate_limited"
AI_AUTH_ERROR = "auth_error"
AI_UNAVAILABLE = "unavailable"
AI_BAD_RESPONSE = "bad_response"
AI_INVALID_REQUEST = "invalid_request"
AI_ERROR = "error"


@dataclass
class AIOutcome:
    """Result of one AI call. ``ask_json`` never raises: every failure becomes a
    non-``ok`` status with a human-readable ``message`` so callers can fall back to
    the deterministic result and the UI can say exactly what went wrong."""

    status: str
    message: str
    data: Any = None
    model: str | None = None
    provider: str | None = None
    latency_ms: int = 0
    timeout_seconds: int | None = None

    @property
    def ok(self) -> bool:
        return self.status == AI_OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "model": self.model,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "timeout_seconds": self.timeout_seconds,
        }


_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$")


def extract_json(text: str) -> Any:
    """Parse a model reply as JSON, tolerating markdown fences and surrounding prose."""
    cleaned = _FENCE_RE.sub("", (text or "").strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start = min((i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1), default=-1)
    if start == -1:
        raise ValueError("no JSON object found in the model reply")
    opener, closer = ("{", "}") if cleaned[start] == "{" else ("[", "]")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start : i + 1])
    raise ValueError("unterminated JSON in the model reply")


class LLMProvider(ABC):
    """Pluggable LLM provider interface."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> str:
        """Return the raw model output as a string."""


class NoOpLLMProvider(LLMProvider):
    """Default provider used when LLM is disabled or not configured."""

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> str:
        return ""


class OpenAICompatibleProvider(LLMProvider):
    """HTTP-based provider compatible with Anthropic, OpenAI-style and Azure/DIAL APIs.

    This keeps the integration pluggable without forcing a vendor dependency into
    the application runtime. Any model behind an OpenAI-compatible endpoint can be
    configured via environment variables.
    """

    @staticmethod
    def _classify_http_error(status_code: int | None, detail: str) -> tuple[str, str]:
        text = detail.lower()
        if status_code == 429 or "rate limit" in text or "quota" in text or "exhausted" in text:
            return (
                AI_RATE_LIMITED,
                "The AI limit has been reached (rate limit or token quota exhausted). Try again in a minute, or continue without AI.",
            )
        if status_code in (401, 403) or "invalid api" in text or "api key" in text or "authentication" in text:
            return (
                AI_AUTH_ERROR,
                "The AI API key was rejected (invalid, expired or without access to this model). Update LLM_API_KEY, or continue without AI.",
            )
        if status_code == 404:
            return (
                AI_INVALID_REQUEST,
                "The configured AI model or deployment was not found. Check LLM_MODEL and LLM_BASE_URL.",
            )
        if status_code == 408 or status_code == 504 or "timeout" in text or "timed out" in text:
            return (AI_TIMEOUT, "The AI service timed out before answering. Retry, or continue without AI.")
        if status_code == 400 or "invalid request" in text:
            return (
                AI_INVALID_REQUEST,
                "The AI provider rejected the request as malformed or unsupported for this model.",
            )
        if status_code is None or status_code >= 500 or "temporar" in text or "unreachable" in text:
            return (
                AI_UNAVAILABLE,
                "The AI provider is currently unavailable. The deterministic flow still works; retry AI later.",
            )
        return (AI_ERROR, "The AI provider returned an error. Retry, or review the provider settings.")

    _DEFAULT_BASE_URLS = {
        "openai": "https://api.openai.com/v1",
        "anthropic": "https://api.anthropic.com",
        "openai_compatible": "https://api.openai.com/v1",
        "generic": "https://api.openai.com/v1",
    }

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str | None,
        provider: str = "openai",
        base_url: str | None = None,
        timeout_seconds: int = 30,
        api_version: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self.provider = (provider or "openai").lower()
        self.api_key = api_key
        self.model = model or self._default_model_for_provider(self.provider)
        self.base_url = (base_url or self._DEFAULT_BASE_URLS.get(self.provider, self._DEFAULT_BASE_URLS["generic"]))
        self.api_version = api_version or self._default_api_version_for_provider(self.provider)
        self.timeout_seconds = timeout_seconds
        self.reasoning_effort = (reasoning_effort or "").strip() or None

    @property
    def _is_azure_style(self) -> bool:
        return self.provider in {"azure", "azure_openai", "dial"}

    @staticmethod
    def _default_model_for_provider(provider: str) -> str:
        return {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "openai_compatible": "gpt-4o-mini",
            "generic": "gpt-4o-mini",
            "azure": "gpt-5-mini-2025-08-07",
            "azure_openai": "gpt-5-mini-2025-08-07",
            "dial": "gpt-5-mini-2025-08-07",
        }.get(provider, "gpt-4o-mini")

    @staticmethod
    def _default_api_version_for_provider(provider: str) -> str | None:
        if provider in {"azure", "azure_openai", "dial"}:
            return "2025-04-01-preview"
        return None

    def _post(self, endpoint: str, headers: dict[str, str], payload: dict[str, Any], timeout: float) -> str:
        """Blocking HTTP round trip; always runs in a worker thread (see ``complete``)."""
        request = Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        details = {"provider": self.provider, "model": self.model}
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            status_code = getattr(exc, "code", None)
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            kind, message = self._classify_http_error(status_code, detail)
            raise LLMError(message, details={"status_code": status_code, "kind": kind, **details}) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMError(
                f"The AI did not answer within {timeout:g}s. Retry, or continue without AI.",
                details={"kind": AI_TIMEOUT, **details},
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMError(
                    f"The AI did not answer within {timeout:g}s. Retry, or continue without AI.",
                    details={"kind": AI_TIMEOUT, **details},
                ) from exc
            raise LLMError(
                "The AI provider is unreachable. Check network access and the configured endpoint, or continue without AI.",
                details={"kind": AI_UNAVAILABLE, "error": str(exc.reason), **details},
            ) from exc
        except OSError as exc:  # connection reset, SSL failure, ...
            raise LLMError(
                "The connection to the AI provider failed. Retry, or continue without AI.",
                details={"kind": AI_UNAVAILABLE, "error": str(exc), **details},
            ) from exc

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.0,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.api_key:
            raise LLMError(
                "AI is enabled but no API key is configured. Set LLM_API_KEY, or continue without AI.",
                details={"kind": AI_AUTH_ERROR, "provider": self.provider, "model": self.model},
            )
        if not self.model:
            raise LLMError(
                "AI model is missing. Set LLM_MODEL or configure the provider default.",
                details={"kind": AI_INVALID_REQUEST, "provider": self.provider},
            )

        endpoint, headers, payload = self._build_request(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        timeout = float(timeout_seconds or self.timeout_seconds)
        body = await asyncio.to_thread(self._post, endpoint, headers, payload, timeout)
        try:
            response_json = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LLMError(
                "The AI provider returned a reply that is not valid JSON.",
                details={"kind": AI_BAD_RESPONSE, "provider": self.provider, "model": self.model},
            ) from exc
        return self._extract_text(response_json)

    def _build_request(
        self,
        prompt: str,
        *,
        system: str | None,
        max_tokens: int | None,
        temperature: float,
    ) -> tuple[str, dict[str, str], dict[str, Any]]:
        if self.provider == "anthropic":
            endpoint = f"{self.base_url.rstrip('/')}/v1/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": "2023-06-01",
            }
            payload = {
                "model": self.model,
                "max_tokens": max_tokens or 2000,
                "temperature": temperature,
                "system": system or _DEFAULT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }
            return endpoint, headers, payload

        if self._is_azure_style:
            base = self.base_url.rstrip("/")
            endpoint = f"{base}/openai/deployments/{self.model}/chat/completions"
            if self.api_version:
                endpoint = f"{endpoint}?api-version={quote(self.api_version)}"
            headers = {
                "Content-Type": "application/json",
                "Api-Key": self.api_key or "",
            }
            messages: list[dict[str, str]] = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            payload = {
                "messages": messages,
                # Reasoning models spend part of this budget on hidden reasoning tokens.
                "max_completion_tokens": max_tokens or 2000,
            }
            if temperature != 0:
                payload["temperature"] = temperature
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
            return endpoint, headers, payload

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key or ''}",
        }
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 2000,
        }
        return endpoint, headers, payload

    @staticmethod
    def _extract_text(response_json: dict[str, Any]) -> str:
        text: str | None = None
        finish_reason = None
        if isinstance(response_json.get("choices"), list) and response_json["choices"]:
            choice = response_json["choices"][0]
            finish_reason = choice.get("finish_reason")
            message = choice.get("message", {})
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    text = content
                elif isinstance(content, list):
                    text = "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
        elif isinstance(response_json.get("content"), list) and response_json["content"]:
            first = response_json["content"][0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                text = first["text"]
        if text is None:
            raise LLMError(
                "The AI provider returned an unexpected response shape.", details={"kind": AI_BAD_RESPONSE}
            )
        if not text.strip():
            hint = " (the token budget ran out before the answer; raise LLM_MAX_TOKENS)" if finish_reason == "length" else ""
            raise LLMError(f"The AI returned an empty answer{hint}.", details={"kind": AI_BAD_RESPONSE})
        return text


def build_llm_provider(settings: Settings | None = None) -> LLMProvider:
    settings = settings or get_settings()
    if not settings.llm_enabled or settings.llm_provider in {"disabled", "off", "none"}:
        return NoOpLLMProvider()
    if settings.llm_provider in {"mock", "noop"}:
        return NoOpLLMProvider()
    return OpenAICompatibleProvider(
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        provider=settings.llm_provider,
        base_url=settings.llm_base_url,
        timeout_seconds=settings.llm_timeout_seconds,
        api_version=settings.llm_api_version,
        reasoning_effort=settings.llm_reasoning_effort,
    )


class LLMService:
    """Thin application facade around the configured provider."""

    def __init__(self, provider: LLMProvider | None = None, *, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = provider or build_llm_provider(self.settings)

    def is_available(self) -> bool:
        return (
            self.settings.llm_enabled
            and self.settings.llm_provider not in {"disabled", "off", "none"}
            and (self.settings.llm_provider in {"mock", "noop"} or bool(self.settings.llm_api_key or self.settings.llm_model))
        )

    def status(self) -> dict[str, Any]:
        """What the UI shows before any call: is AI usable, with which model, and if not, why."""
        s = self.settings
        reason: str | None = None
        if not s.llm_enabled or s.llm_provider in {"disabled", "off", "none"}:
            reason = "AI is switched off (LLM_ENABLED=false). The deterministic flow is used."
        elif s.llm_provider not in {"mock", "noop"} and not s.llm_api_key:
            reason = "AI is enabled but no API key is configured (LLM_API_KEY)."
        return {
            "available": self.is_available() and reason is None,
            "enabled": bool(s.llm_enabled),
            "provider": s.llm_provider,
            "model": s.llm_model,
            "timeout_seconds": s.llm_timeout_seconds,
            "reason": reason,
        }

    @staticmethod
    def _compact_context(context: Any) -> str:
        return json.dumps(context, ensure_ascii=False, default=str, indent=2, sort_keys=True)

    def _build_prompt(self, question: str, context: Any) -> str:
        return (
            "Question:\n"
            f"{question}\n\n"
            "Context:\n"
            f"{self._compact_context(context)}\n\n"
            "Instruction:\n"
            "- Interpret the evidence, not the raw file contents.\n"
            "- Do not alter or approve a financial decision.\n"
            "- Return concise JSON with keys: verdict, explanation, recommendation, confidence.\n"
            "- Confidence is a value between 0.0 and 1.0.\n"
            "- If the data is insufficient, say so clearly and offer a safer fallback."
        )

    async def ask_json(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
        timeout_seconds: float | None = None,
    ) -> AIOutcome:
        """One bounded model call whose reply must be a JSON document. Never raises."""
        provider_name, model = self.settings.llm_provider, self.settings.llm_model
        timeout = float(timeout_seconds or self.settings.llm_timeout_seconds)
        if not self.is_available():
            return AIOutcome(
                AI_DISABLED,
                self.status()["reason"] or "AI is not configured. The deterministic flow is used.",
                model=model,
                provider=provider_name,
                timeout_seconds=int(timeout),
            )
        started = time.monotonic()

        def done(status: str, message: str, data: Any = None) -> AIOutcome:
            return AIOutcome(
                status,
                message,
                data,
                model=model,
                provider=provider_name,
                latency_ms=int((time.monotonic() - started) * 1000),
                timeout_seconds=int(timeout),
            )

        try:
            # ``timeout`` is also handed to the HTTP layer; wait_for is the hard stop for
            # providers that ignore it (and the worker thread is abandoned, never awaited).
            raw = await asyncio.wait_for(
                self.provider.complete(
                    prompt,
                    system=system or self.settings.llm_system_prompt or _DEFAULT_SYSTEM_PROMPT,
                    max_tokens=max_tokens or self.settings.llm_max_tokens,
                    temperature=0.0,
                    timeout_seconds=timeout,
                ),
                timeout=timeout + 5,
            )
        except asyncio.TimeoutError:
            return done(AI_TIMEOUT, f"The AI did not answer within {timeout:g}s. Retry, or continue without AI.")
        except LLMError as exc:
            first = exc.details[0] if exc.details and isinstance(exc.details[0], dict) else {}
            return done(str(first.get("kind") or AI_ERROR), exc.message)
        except Exception as exc:  # noqa: BLE001 - a model failure must never break the workflow
            return done(AI_ERROR, f"Unexpected AI error ({type(exc).__name__}). The deterministic flow is used.")

        try:
            data = extract_json(raw)
        except ValueError:
            return done(AI_BAD_RESPONSE, "The AI replied, but not with usable JSON. The deterministic result is used.")
        return done(AI_OK, "AI answered.", data)

    def answer(self, question: str, context: Any) -> dict[str, Any]:
        """Synchronous convenience wrapper (generic Q&A). Kept for callers outside the async flows."""
        if not self.is_available():
            return {
                "status": "disabled",
                "message": (
                    "LLM is not configured. Set LLM_ENABLED=true, choose a provider/model, and provide "
                    "LLM_API_KEY before enabling semantic AI hints. The deterministic workflow will continue without AI."
                ),
            }

        prompt = self._build_prompt(question, context)
        coro = self.ask_json(prompt)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            outcome = asyncio.run(coro)
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                outcome = executor.submit(asyncio.run, coro).result()

        if not outcome.ok:
            return {"status": outcome.status, "message": outcome.message}
        return {
            "status": "ok",
            "model": self.settings.llm_model,
            "provider": self.settings.llm_provider,
            "answer": outcome.data,
        }


def build_llm_service(settings: Settings | None = None) -> LLMService:
    settings = settings or get_settings()
    return LLMService(settings=settings)
