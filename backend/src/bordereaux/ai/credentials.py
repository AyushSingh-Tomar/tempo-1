"""Per-user AI API keys.

A user can give the app their own API key (Settings -> AI connection). It is used for that
user's AI calls instead of the server's key, against the *same provider configuration* the app
already uses (provider, model, endpoint, API version) - a user key only replaces the secret.

Handling rules:
* encrypted at rest with Fernet; the master key comes from ``SECRETS_KEY`` or, if unset, from a
  random key file generated once under the storage root (``.secrets/fernet.key``);
* never returned by any endpoint, never logged, never put in audit payloads - only the last 4
  characters (``key_hint``) are shown back to the user;
* verified with a real minimal call before it is saved (the user can opt to save untested, e.g.
  when the provider is temporarily unreachable).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Callable
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bordereaux.ai.service import AIOutcome, LLMService, build_llm_service
from bordereaux.config import Settings, get_settings
from bordereaux.core.utils import utcnow
from bordereaux.models.ai_credential import UserAICredential

_DISABLED = {"", "disabled", "off", "none"}
#: Provider configuration used when the server itself has none (a user key still has to talk to *some* provider).
DEFAULT_PROVIDER_CONFIG = {
    "llm_provider": "dial",
    "llm_model": "gpt-5-mini-2025-08-07",
    "llm_base_url": "https://ai-proxy.lab.epam.com",
    "llm_api_version": "2025-04-01-preview",
}
KEY_PATTERN = re.compile(r"^[\x21-\x7e]{8,512}$")  # printable ASCII, no whitespace
TEST_TIMEOUT_SECONDS = 30


class InvalidKeyFormat(ValueError):
    pass


def normalize_key(raw: str) -> str:
    """Strip surrounding whitespace / quotes users commonly paste; reject anything that cannot be a key."""
    key = (raw or "").strip().strip("\"'").strip()
    if not KEY_PATTERN.match(key):
        raise InvalidKeyFormat("That does not look like an API key (8-512 visible characters, no spaces).")
    return key


# ------------------------------------------------------------------ encryption


def _fernet(settings: Settings | None = None) -> Fernet:
    settings = settings or get_settings()
    configured = os.environ.get("SECRETS_KEY") or getattr(settings, "secrets_key", None)
    if configured:
        return Fernet(configured.encode() if isinstance(configured, str) else configured)
    path = Path(settings.storage_root) / ".secrets" / "fernet.key"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(Fernet.generate_key())
        try:
            path.chmod(0o600)
        except OSError:  # pragma: no cover - best effort (Windows)
            pass
    return Fernet(path.read_bytes().strip())


def encrypt_key(key: str, settings: Settings | None = None) -> str:
    return _fernet(settings).encrypt(key.encode()).decode()


def decrypt_key(token: str, settings: Settings | None = None) -> str | None:
    try:
        return _fernet(settings).decrypt(token.encode()).decode()
    except InvalidToken:  # master key changed: treat as "no key" rather than crash the AI step
        return None


def key_hint(key: str) -> str:
    return key[-4:]


# ------------------------------------------------------------------ storage


async def get_credential(db: AsyncSession, user_id: UUID) -> UserAICredential | None:
    return (await db.execute(select(UserAICredential).where(UserAICredential.user_id == user_id))).scalar_one_or_none()


async def get_user_key(db: AsyncSession, user_id: UUID | None) -> str | None:
    if user_id is None:
        return None
    row = await get_credential(db, user_id)
    return decrypt_key(row.encrypted_key) if row else None


async def save_user_key(db: AsyncSession, user_id: UUID, key: str, *, validated: bool) -> UserAICredential:
    row = await get_credential(db, user_id)
    if row is None:
        row = UserAICredential(user_id=user_id, encrypted_key="", key_hint="")
        db.add(row)
    row.encrypted_key = encrypt_key(key)
    row.key_hint = key_hint(key)
    row.validated_at = utcnow() if validated else None
    await db.flush()
    return row


async def delete_user_key(db: AsyncSession, user_id: UUID) -> bool:
    row = await get_credential(db, user_id)
    if row is None:
        return False
    await db.delete(row)
    await db.flush()
    return True


# ------------------------------------------------------------------ using a key


def settings_with_key(key: str, base: Settings | None = None) -> Settings:
    """The app's AI configuration with ``key`` swapped in (and the default provider if the server has none)."""
    base = base or get_settings()
    update: dict[str, object] = {"llm_enabled": True, "llm_api_key": key}
    if (base.llm_provider or "").lower() in _DISABLED or not base.llm_model:
        update.update(DEFAULT_PROVIDER_CONFIG)
    return base.model_copy(update=update)


def service_for_key(key: str) -> LLMService:
    return LLMService(settings=settings_with_key(key))


async def resolve_llm_service(
    db: AsyncSession, user_id: UUID | None, factory: Callable[[], LLMService] = build_llm_service
) -> tuple[LLMService, str]:
    """The AI service to use for ``user_id``'s calls and where its key comes from:
    ``"user"`` (their own key), ``"server"`` (configured in the environment) or ``"none"``."""
    key = await get_user_key(db, user_id)
    if key:
        return service_for_key(key), "user"
    service = factory()
    return service, ("server" if service.is_available() and service.settings.llm_api_key else "none")


async def check_key(key: str) -> AIOutcome:
    """One minimal real call with ``key`` - the only way to know it works with the configured provider."""
    service = service_for_key(key)
    return await service.ask_json(
        'Reply with exactly this JSON and nothing else: {"ok": true}',
        system="You are a connectivity check. Reply with JSON only.",
        max_tokens=400,
        timeout_seconds=TEST_TIMEOUT_SECONDS,
    )
