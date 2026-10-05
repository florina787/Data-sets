"""Runtime configuration. Secrets come from the environment only and are never logged."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = field(default_factory=lambda: _bool("DEMO_MODE", True))
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./lexguard.db"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("LEXGUARD_DATA_DIR", str(REPO_ROOT / "synthetic_data"))))
    max_agent_steps: int = field(default_factory=lambda: int(os.getenv("MAX_AGENT_STEPS", "12")))
    max_tool_calls: int = field(default_factory=lambda: int(os.getenv("MAX_TOOL_CALLS", "40")))
    request_timeout_s: float = field(default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_S", "20")))
    cors_origins: tuple[str, ...] = field(default_factory=lambda: tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()))
    llm_model: str = field(default_factory=lambda: os.getenv("LEXGUARD_LLM_MODEL", "claude-sonnet-5-5"))
    # Never printed, never logged. Only read when demo_mode is False.
    _anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"), repr=False)

    @property
    def live_llm_enabled(self) -> bool:
        return (not self.demo_mode) and bool(self._anthropic_api_key)

    def anthropic_api_key(self) -> str | None:
        return None if self.demo_mode else self._anthropic_api_key

    def public_view(self) -> dict:
        return {
            "demo_mode": self.demo_mode,
            "live_llm_enabled": self.live_llm_enabled,
            "database": self.database_url.split(":", 1)[0],
            "max_agent_steps": self.max_agent_steps,
            "max_tool_calls": self.max_tool_calls,
            "request_timeout_s": self.request_timeout_s,
            "llm_model": self.llm_model if self.live_llm_enabled else None,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
