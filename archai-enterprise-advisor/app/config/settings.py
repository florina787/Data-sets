"""Runtime settings.

All configuration comes from environment variables (optionally a local ``.env``
file that is git-ignored). Secrets are held as :class:`pydantic.SecretStr` so
they are never rendered in ``repr``/logs, and they are never returned by the API.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
SCENARIOS_DIR = PROJECT_ROOT / "scenarios"


class Settings(BaseSettings):
    """Application settings, resolved from the environment on every call."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(default="claude-sonnet-5-5", alias="ARCHAI_LLM_MODEL")
    llm_max_tokens: int = Field(default=900, alias="ARCHAI_LLM_MAX_TOKENS")
    llm_timeout_seconds: float = Field(default=30.0, alias="ARCHAI_LLM_TIMEOUT_SECONDS")
    log_level: str = Field(default="INFO", alias="ARCHAI_LOG_LEVEL")
    pricing_file: Path = Field(default=CONFIG_DIR / "model_pricing.json", alias="ARCHAI_PRICING_FILE")

    @property
    def has_api_key(self) -> bool:
        """True when a non-placeholder API key is configured (value never exposed)."""
        if self.anthropic_api_key is None:
            return False
        value = self.anthropic_api_key.get_secret_value().strip()
        return bool(value) and value != "your_own_key_here"

    @property
    def live_ai_enabled(self) -> bool:
        """Live AI narration is only used when demo mode is off AND a key exists."""
        return (not self.demo_mode) and self.has_api_key

    @property
    def mode_label(self) -> str:
        if self.demo_mode:
            return "DEMO"
        return "LIVE_AI" if self.has_api_key else "LIVE_AI_UNCONFIGURED (deterministic fallback)"


def get_settings() -> Settings:
    """Return fresh settings (cheap; lets tests change env vars safely)."""
    return Settings()
