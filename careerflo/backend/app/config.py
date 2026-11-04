"""Runtime configuration. Every secret comes from the environment; nothing is hard-coded."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Career_flo AI"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite:///./careerflo.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    public_app_url: str = "http://localhost:5173"
    admin_emails: str = ""

    # --- Authentication -------------------------------------------------
    # "supabase": verify Supabase Auth access tokens (production).
    # "local": the backend issues its own tokens (development / tests / self-host without Supabase).
    auth_mode: Literal["supabase", "local"] = "local"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""  # legacy HS256 projects
    supabase_jwt_audience: str = "authenticated"
    local_jwt_secret: str = Field(default="dev-only-change-me-dev-only-change-me", min_length=32)
    local_token_ttl_minutes: int = 60 * 12

    # --- Qwen inference (open-weight only) ------------------------------
    # "ollama" and "llamacpp" both expose an OpenAI-compatible endpoint.
    # "scripted" is a deterministic stand-in used by automated tests.
    # "disabled" runs every feature on its deterministic path only.
    llm_provider: Literal["ollama", "llamacpp", "scripted", "disabled"] = "ollama"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen3:1.7b"
    llm_timeout_seconds: float = 120.0
    llm_max_concurrency: int = 1
    llm_max_tokens: int = 700

    # --- Job providers --------------------------------------------------
    jsearch_api_key: str = ""
    jsearch_host: str = "jsearch.p.rapidapi.com"
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    job_cache_ttl_seconds: int = 60 * 30
    provider_daily_quota: int = 200
    enable_synthetic_jobs: bool = True

    # --- GitHub ----------------------------------------------------------
    github_token: str = ""

    # --- Stripe (test mode until explicitly authorised) -----------------
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_pro: str = ""
    stripe_price_premium: str = ""
    stripe_allow_live: bool = False

    # --- Limits ----------------------------------------------------------
    rate_limit_per_minute: int = 60
    max_upload_bytes: int = 5 * 1024 * 1024
    reservation_stale_minutes: int = 15

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
