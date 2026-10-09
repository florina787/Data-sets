"""Environment-based configuration.

All values are read from environment variables (see ../../.env.example).
Policy thresholds here are configurable synthetic rules, not any operator's
real policy.
"""
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


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


@dataclass(frozen=True)
class Settings:
    # demo | production. Production disables persona login, seed and reset.
    app_mode: str = "demo"
    database_url: str = ""
    checkpoint_url: str = ""
    # DEMO | LIVE | HYBRID — how text/structured outputs are generated.
    generation_mode: str = "DEMO"
    # SIMULATED is the only connector mode implemented in this prototype.
    connector_mode: str = "SIMULATED"
    session_secret: str = "dev-only-insecure-secret-change-me"
    session_ttl_minutes: int = 480

    # LLM provider (LIVE / HYBRID only). Credentials stay server-side.
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-5-5"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 1500
    llm_max_concurrency: int = 4
    llm_case_token_budget: int = 40000
    llm_circuit_breaker_failures: int = 3
    llm_circuit_breaker_reset_seconds: int = 60
    # Pricing per million tokens, with the date the figures were configured.
    llm_price_input_per_mtok: float = 0.0
    llm_price_output_per_mtok: float = 0.0
    llm_pricing_configured_on: str = "unset"

    # Workflow limits
    max_evidence_iterations: int = 2
    max_investigation_seconds: int = 120

    # Synthetic evidence rules
    diagnostic_freshness_hours: int = 24
    incident_window_slack_minutes: int = 30
    approval_ttl_minutes: int = 60
    recovery_window_minutes: int = 30
    recovery_min_samples: int = 4
    repeat_contact_window_days: int = 30

    data_dir: Path = field(default=REPO_ROOT / "data")
    evaluation_dir: Path = field(default=REPO_ROOT / "evaluation")
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @property
    def is_demo(self) -> bool:
        return self.app_mode == "demo"


@lru_cache
def get_settings() -> Settings:
    default_db = f"sqlite:///{REPO_ROOT / 'backend' / 'telecomresolve.db'}"
    db_url = os.getenv("DATABASE_URL", default_db)
    cp_default = (
        f"sqlite:///{REPO_ROOT / 'backend' / 'checkpoints.db'}"
        if db_url.startswith("sqlite")
        else db_url
    )
    mode = os.getenv("APP_MODE", "demo").lower()
    secret = os.getenv("SESSION_SECRET", Settings.session_secret)
    if mode == "production" and secret == Settings.session_secret:
        raise RuntimeError("SESSION_SECRET must be set in production mode")
    gen_mode = os.getenv("GENERATION_MODE", "DEMO").upper()
    if gen_mode not in {"DEMO", "LIVE", "HYBRID"}:
        raise RuntimeError(f"Unsupported GENERATION_MODE {gen_mode}")
    return Settings(
        app_mode=mode,
        database_url=db_url,
        checkpoint_url=os.getenv("CHECKPOINT_URL", cp_default),
        generation_mode=gen_mode,
        connector_mode=os.getenv("CONNECTOR_MODE", "SIMULATED").upper(),
        session_secret=secret,
        session_ttl_minutes=_int("SESSION_TTL_MINUTES", 480),
        llm_provider=os.getenv("LLM_PROVIDER", "anthropic"),
        llm_model=os.getenv("LLM_MODEL", "claude-opus-5-5"),
        llm_api_key=os.getenv("LLM_API_KEY", os.getenv("ANTHROPIC_API_KEY", "")),
        llm_timeout_seconds=_float("LLM_TIMEOUT_SECONDS", 30.0),
        llm_max_retries=_int("LLM_MAX_RETRIES", 2),
        llm_max_output_tokens=_int("LLM_MAX_OUTPUT_TOKENS", 1500),
        llm_max_concurrency=_int("LLM_MAX_CONCURRENCY", 4),
        llm_case_token_budget=_int("LLM_CASE_TOKEN_BUDGET", 40000),
        llm_circuit_breaker_failures=_int("LLM_CIRCUIT_BREAKER_FAILURES", 3),
        llm_circuit_breaker_reset_seconds=_int("LLM_CIRCUIT_BREAKER_RESET_SECONDS", 60),
        llm_price_input_per_mtok=_float("LLM_PRICE_INPUT_PER_MTOK", 0.0),
        llm_price_output_per_mtok=_float("LLM_PRICE_OUTPUT_PER_MTOK", 0.0),
        llm_pricing_configured_on=os.getenv("LLM_PRICING_CONFIGURED_ON", "unset"),
        max_evidence_iterations=_int("MAX_EVIDENCE_ITERATIONS", 2),
        max_investigation_seconds=_int("MAX_INVESTIGATION_SECONDS", 120),
        diagnostic_freshness_hours=_int("DIAGNOSTIC_FRESHNESS_HOURS", 24),
        incident_window_slack_minutes=_int("INCIDENT_WINDOW_SLACK_MINUTES", 30),
        approval_ttl_minutes=_int("APPROVAL_TTL_MINUTES", 60),
        recovery_window_minutes=_int("RECOVERY_WINDOW_MINUTES", 30),
        recovery_min_samples=_int("RECOVERY_MIN_SAMPLES", 4),
        repeat_contact_window_days=_int("REPEAT_CONTACT_WINDOW_DAYS", 30),
        cors_origins=tuple(
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if o.strip()
        ),
    )
