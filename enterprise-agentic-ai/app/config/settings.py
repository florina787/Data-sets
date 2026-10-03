"""Application settings loaded from environment variables.

Secrets are only ever read from the environment (or a local, git-ignored ``.env``
file) and are stored as :class:`pydantic.SecretStr` so they are never printed in
logs, reprs or API responses.
"""

from __future__ import annotations

import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class AppMode(str, Enum):
    """Runtime mode of the copilot."""

    DEMO = "demo"  # default: zero paid LLM calls, deterministic offline synthesis
    LIVE = "live"  # Anthropic Claude via LangChain; requires ANTHROPIC_API_KEY


class EmbeddingProvider(str, Enum):
    """Embedding backend used by the RAG pipeline."""

    SENTENCE_TRANSFORMERS = "sentence-transformers"
    HASHING = "hashing"


class ConfigurationError(RuntimeError):
    """Raised when the environment is configured inconsistently."""


class Settings(BaseSettings):
    """Typed, validated application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Enterprise Agentic AI Copilot"
    app_mode: AppMode = AppMode.DEMO
    log_level: str = "INFO"

    # --- LLM (LIVE mode only) ---------------------------------------------
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    # Unset by default: some Claude models only accept the default temperature.
    llm_temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    llm_max_tokens: int = Field(default=1500, ge=64, le=8192)
    llm_timeout_seconds: float = Field(default=60.0, gt=0)

    # --- RAG -------------------------------------------------------------
    embedding_provider: EmbeddingProvider = EmbeddingProvider.SENTENCE_TRANSFORMERS
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_dir: Path = PROJECT_ROOT / "data" / "chroma"
    chroma_collection: str = "enterprise_docs"
    documents_dir: Path = PROJECT_ROOT / "data" / "documents"
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    chunk_size: int = Field(default=800, ge=100, le=4000)
    chunk_overlap: int = Field(default=120, ge=0, le=1000)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    min_relevance_score: float = Field(default=0.12, ge=0.0, le=1.0)

    # --- Tools / data ----------------------------------------------------
    synthetic_data_dir: Path = PROJECT_ROOT / "data" / "synthetic"

    # --- Guardrails ------------------------------------------------------
    confidence_threshold: float = Field(default=0.45, ge=0.0, le=1.0)
    corporate_email_domain: str = "novagrid.example"

    # --- Observability ---------------------------------------------------
    trace_dir: Path = PROJECT_ROOT / "data" / "traces"
    trace_buffer_size: int = Field(default=500, ge=10)

    # --- Uploads ---------------------------------------------------------
    max_upload_mb: float = Field(default=5.0, gt=0, le=50)
    allow_uploads: bool = True

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, value: str) -> str:
        value = value.upper()
        if value not in logging.getLevelNamesMapping():
            raise ValueError(f"Unknown log level: {value}")
        return value

    @field_validator("anthropic_api_key", mode="before")
    @classmethod
    def _empty_key_is_none(cls, value: object) -> object:
        # Treat blank values and the .env.example placeholder as "not set".
        if value is None:
            return None
        text = str(value.get_secret_value() if isinstance(value, SecretStr) else value).strip()
        if not text or text in {"your_api_key_here", "your_key_here"}:
            return None
        return text

    @model_validator(mode="after")
    def _validate_mode(self) -> "Settings":
        if self.chunk_overlap >= self.chunk_size:
            raise ConfigurationError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        if self.app_mode is AppMode.LIVE and self.anthropic_api_key is None:
            raise ConfigurationError(
                "APP_MODE=live requires ANTHROPIC_API_KEY to be set in the environment. "
                "Unset APP_MODE (or set APP_MODE=demo) to run without an API key."
            )
        return self

    @property
    def is_live(self) -> bool:
        """True when real Claude calls are enabled."""
        return self.app_mode is AppMode.LIVE

    def public_summary(self) -> dict[str, object]:
        """Non-sensitive configuration that is safe to expose via the API."""
        return {
            "app_name": self.app_name,
            "mode": self.app_mode.value,
            "llm_model": self.anthropic_model if self.is_live else None,
            "embedding_provider": self.embedding_provider.value,
            "retrieval_top_k": self.retrieval_top_k,
            "uploads_enabled": self.allow_uploads,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
