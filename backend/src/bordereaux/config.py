"""Application settings, loaded from environment variables and an optional `.env` file.

Every setting can be overridden with an environment variable of the same name
(case-insensitive), e.g. ``DATABASE_URL=sqlite+aiosqlite:///./other.db``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Bordereaux Intelligence Platform"
    environment: str = Field(default="development", description="development | test | production")
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"

    # --- Database -------------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./bordereaux.db"
    database_echo: bool = False
    # Apply Alembic migrations at startup (SQLite only) so a fresh checkout works without manual setup.
    auto_migrate: bool = True

    # --- Storage --------------------------------------------------------
    storage_backend: str = Field(default="local", description="Only 'local' is implemented in iteration 1")
    storage_root: Path = Path("./storage")
    max_upload_bytes: int = 100 * 1024 * 1024  # 100MB, SECURITY_AND_AUDIT.md §6.3

    # --- Auth -----------------------------------------------------------
    auth_provider: str = Field(default="dev", description="Only 'dev' is implemented in iteration 1")
    # Comma-separated allow-list of dev tokens (without the "Bearer " prefix),
    # e.g. "dev-analyst1-analyst,dev-rev1-reviewer". Empty = any well-formed
    # dev token is accepted (local development only).
    dev_auth_tokens: str = ""

    # --- Jobs -----------------------------------------------------------
    jobs_max_concurrent_per_project: int = 3

    # --- CORS (frontend dev server) -------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Optional LLM ----------------------------------------------------
    llm_enabled: bool = False
    # Fernet key that encrypts user-supplied API keys at rest. Unset = a random key file is created under storage_root.
    secrets_key: str | None = None
    llm_provider: str = "disabled"
    llm_model: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_api_version: str | None = None
    llm_timeout_seconds: int = 30
    llm_max_tokens: int = 6000
    # Reasoning models (gpt-5 family) answer much faster with "low"; empty = do not send the parameter.
    llm_reasoning_effort: str | None = "low"
    llm_system_prompt: str = (
        "You are an interpretation assistant for a reinsurance bordereaux workflow. "
        "Use only the provided evidence; never change the underlying financial state, "
        "never fabricate a mapping or a discrepancy outcome, and return a compact JSON object."
    )

    @property
    def dev_auth_token_list(self) -> list[str]:
        return [t.strip() for t in self.dev_auth_tokens.split(",") if t.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
