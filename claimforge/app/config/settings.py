"""Application configuration.

All configuration comes from environment variables (optionally a local, git-ignored
``.env`` file). Secrets such as ``ANTHROPIC_API_KEY`` are held privately on the
settings object, are never included in ``repr``/``public_dict`` output, are never
logged and are never returned through the API or UI.

DEMO_MODE defaults to ``true``: no paid LLM calls are made and no API key is needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_DATA_DIR = PROJECT_ROOT / "synthetic_data"

SYNTHETIC_BANNER = "SYNTHETIC DEMO DATA — NOT FOR REAL CLAIM ADJUDICATION."


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency). Existing env vars always win."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int, lo: int, hi: int) -> int:
    try:
        parsed = int(value) if value not in (None, "") else default
    except ValueError:
        parsed = default
    return max(lo, min(hi, parsed))


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Runtime settings. Construct via :func:`load_settings` / :func:`get_settings`."""

    demo_mode: bool = True
    random_seed: int = 42
    max_agent_iterations: int = 8
    max_tool_calls: int = 20
    max_workflow_steps: int = 60
    agent_timeout_seconds: float = 30.0
    default_claim_count: int = 10_000
    max_claim_count: int = 100_000
    anomaly_relative_threshold: float = 0.15
    anomaly_z_threshold: float = 3.0
    max_upload_bytes: int = 200_000
    annual_claim_volume: int = 250_000
    anthropic_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = 20.0
    log_level: str = "INFO"
    _anthropic_api_key: str | None = field(default=None, repr=False, compare=False)

    @property
    def anthropic_api_key_configured(self) -> bool:
        return bool(self._anthropic_api_key)

    @property
    def live_ai_enabled(self) -> bool:
        """LLM-assisted narration only when DEMO_MODE=false AND a key is configured."""
        return (not self.demo_mode) and self.anthropic_api_key_configured

    def secret_api_key(self) -> str | None:
        """Internal accessor used only by the LLM client. Never log or return this."""
        return self._anthropic_api_key

    def public_dict(self) -> dict:
        """Safe, secret-free view for /health, UI and logs."""
        return {
            "demo_mode": self.demo_mode,
            "live_ai_enabled": self.live_ai_enabled,
            "anthropic_api_key_configured": self.anthropic_api_key_configured,
            "random_seed": self.random_seed,
            "max_agent_iterations": self.max_agent_iterations,
            "max_tool_calls": self.max_tool_calls,
            "max_workflow_steps": self.max_workflow_steps,
            "agent_timeout_seconds": self.agent_timeout_seconds,
            "default_claim_count": self.default_claim_count,
            "max_claim_count": self.max_claim_count,
            "anomaly_relative_threshold": self.anomaly_relative_threshold,
            "anomaly_z_threshold": self.anomaly_z_threshold,
            "annual_claim_volume": self.annual_claim_volume,
            "anthropic_model": self.anthropic_model if self.live_ai_enabled else None,
        }


def load_settings(**overrides) -> Settings:
    """Read settings from the environment (plus optional overrides, used by tests)."""
    _load_dotenv(PROJECT_ROOT / ".env")
    env = os.environ
    values = dict(
        demo_mode=_as_bool(env.get("DEMO_MODE"), True),
        random_seed=_as_int(env.get("RANDOM_SEED"), 42, 0, 2**31 - 1),
        max_agent_iterations=_as_int(env.get("MAX_AGENT_ITERATIONS"), 8, 1, 50),
        max_tool_calls=_as_int(env.get("MAX_TOOL_CALLS"), 20, 1, 200),
        max_workflow_steps=_as_int(env.get("MAX_WORKFLOW_STEPS"), 60, 3, 200),
        agent_timeout_seconds=_as_float(env.get("AGENT_TIMEOUT_SECONDS"), 30.0),
        default_claim_count=_as_int(env.get("DEFAULT_CLAIM_COUNT"), 10_000, 100, 100_000),
        max_claim_count=_as_int(env.get("MAX_CLAIM_COUNT"), 100_000, 100, 100_000),
        anomaly_relative_threshold=_as_float(env.get("ANOMALY_RELATIVE_THRESHOLD"), 0.15),
        anomaly_z_threshold=_as_float(env.get("ANOMALY_Z_THRESHOLD"), 3.0),
        max_upload_bytes=_as_int(env.get("MAX_UPLOAD_BYTES"), 200_000, 1_000, 2_000_000),
        annual_claim_volume=_as_int(env.get("ANNUAL_CLAIM_VOLUME"), 250_000, 1_000, 10_000_000),
        anthropic_model=env.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        log_level=env.get("LOG_LEVEL", "INFO"),
        _anthropic_api_key=(env.get("ANTHROPIC_API_KEY") or None),
    )
    # Treat the documented placeholder as "not configured".
    if values["_anthropic_api_key"] in {"your_own_key_here", "changeme"}:
        values["_anthropic_api_key"] = None
    values.update(overrides)
    return Settings(**values)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
