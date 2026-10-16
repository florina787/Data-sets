"""Application settings.

All configuration comes from environment variables (or a local ``.env`` file that is
git-ignored). Secrets are never hard-coded and are never sent to the frontend.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

# Placeholder values that must never be accepted as real secrets outside "demo".
_INSECURE_SECRETS = {"", "changeme", "change-me", "secret", "dev", "demo"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MedAccess AI"
    environment: Literal["demo", "development", "test", "staging", "production"] = "demo"
    # Data mode A = synthetic; B = public discovery; C = authorized live integration.
    data_mode: Literal["SYNTHETIC", "PUBLIC_DISCOVERY", "AUTHORIZED_LIVE"] = "SYNTHETIC"

    database_url: str = Field(default=f"sqlite:///{(PROJECT_DIR / 'data' / 'medaccess.db').as_posix()}")
    checkpoint_db_path: str = Field(default=str(PROJECT_DIR / "data" / "checkpoints.sqlite"))
    redis_url: str | None = None

    jwt_secret: SecretStr = SecretStr("")
    jwt_ttl_minutes: int = 120
    field_encryption_key: SecretStr = SecretStr("")

    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

    # LLM (optional). Without a key the copilot runs in deterministic mode.
    anthropic_api_key: SecretStr = SecretStr("")
    llm_enabled: bool = False
    llm_router_model: str = "claude-haiku-5-5"
    llm_explainer_model: str = "claude-sonnet-5-5"
    llm_max_tokens_per_workflow: int = 6000
    llm_max_response_tokens: int = 600

    # LangSmith (optional). Raw payload tracing is off unless explicitly approved.
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr = SecretStr("")
    langsmith_project: str = "medaccess-ai"
    langsmith_allow_raw_payloads: bool = False

    otel_enabled: bool = True
    otel_console_export: bool = False

    # Workflow execution controls
    max_graph_steps: int = 40
    max_workflow_seconds: float = 20.0
    max_tool_calls: int = 60
    max_retries: int = 2
    retry_base_delay_s: float = 0.05
    circuit_failure_threshold: int = 3
    circuit_reset_seconds: float = 30.0

    # Availability verification
    max_verified_age_hours: float = 6.0
    min_source_reliability: float = 0.8

    rate_limit_per_minute: int = 120
    search_retention_days: int = 30
    audit_retention_days: int = 365

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v):
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_production_like(self) -> bool:
        return self.environment in {"staging", "production"}

    @property
    def llm_configured(self) -> bool:
        return self.llm_enabled and bool(self.anthropic_api_key.get_secret_value())

    @property
    def langsmith_configured(self) -> bool:
        return self.langsmith_tracing and bool(self.langsmith_api_key.get_secret_value())


class ConfigurationError(RuntimeError):
    pass


_EPHEMERAL_JWT = secrets.token_urlsafe(48)


def validate_settings(s: Settings) -> list[str]:
    """Startup configuration checks. Raises for fatal problems; returns warnings."""
    warnings: list[str] = []
    jwt = s.jwt_secret.get_secret_value()
    if s.is_production_like:
        if jwt.lower() in _INSECURE_SECRETS or len(jwt) < 32:
            raise ConfigurationError("JWT_SECRET must be set to a strong value (>=32 chars) in staging/production.")
        if s.data_mode == "SYNTHETIC" and s.environment == "production":
            warnings.append("Production environment is running in SYNTHETIC data mode.")
        if s.langsmith_allow_raw_payloads:
            raise ConfigurationError("Raw payload tracing cannot be enabled in staging/production without a "
                                     "documented privacy basis; unset LANGSMITH_ALLOW_RAW_PAYLOADS.")
        if not s.field_encryption_key.get_secret_value():
            raise ConfigurationError("FIELD_ENCRYPTION_KEY is required in staging/production.")
    elif not jwt:
        warnings.append("JWT_SECRET not set - using an ephemeral per-process secret (demo only).")
    if s.llm_enabled and not s.anthropic_api_key.get_secret_value():
        warnings.append("LLM_ENABLED=true but ANTHROPIC_API_KEY is missing - deterministic copilot mode in use.")
    if s.langsmith_tracing and not s.langsmith_api_key.get_secret_value():
        warnings.append("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is missing - tracing disabled.")
    return warnings


def jwt_secret_value(s: Settings) -> str:
    return s.jwt_secret.get_secret_value() or _EPHEMERAL_JWT


@lru_cache
def get_settings() -> Settings:
    return Settings()
