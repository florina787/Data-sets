"""Runtime configuration.

Every knob is an environment variable so the same image runs in dev, CI and
production. Defaults are safe for local development and fully offline: the
mock LLM provider is used unless an Anthropic credential is configured and
``WEALTH_AI_LLM_PROVIDER=anthropic`` is set explicitly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("WEALTH_AI_ENV", "dev"))

    # --- Identity -----------------------------------------------------------
    # Dev uses a shared HS256 secret. Production must use RS256 tokens issued
    # by the corporate IdP and validated against its JWKS endpoint.
    jwt_secret: str = field(default_factory=lambda: _env("WEALTH_AI_JWT_SECRET", "dev-only-secret-change-me-32-bytes!"))
    jwt_issuer: str = field(default_factory=lambda: _env("WEALTH_AI_JWT_ISSUER", "https://idp.dev.example-insurer.internal"))
    jwt_audience: str = field(default_factory=lambda: _env("WEALTH_AI_JWT_AUDIENCE", "wealth-ai-platform"))

    # --- LLM gateway ----------------------------------------------------------
    llm_provider: str = field(default_factory=lambda: _env("WEALTH_AI_LLM_PROVIDER", "mock"))
    llm_timeout_s: float = field(default_factory=lambda: float(_env("WEALTH_AI_LLM_TIMEOUT_S", "30")))
    llm_max_retries: int = field(default_factory=lambda: int(_env("WEALTH_AI_LLM_MAX_RETRIES", "2")))
    llm_cache_ttl_s: int = field(default_factory=lambda: int(_env("WEALTH_AI_LLM_CACHE_TTL_S", "600")))
    breaker_failure_threshold: int = field(default_factory=lambda: int(_env("WEALTH_AI_BREAKER_FAILURES", "5")))
    breaker_reset_s: float = field(default_factory=lambda: float(_env("WEALTH_AI_BREAKER_RESET_S", "30")))

    # --- Rate limiting / budgets ------------------------------------------------
    requests_per_minute: int = field(default_factory=lambda: int(_env("WEALTH_AI_RPM_PER_USER", "60")))
    daily_token_budget: int = field(default_factory=lambda: int(_env("WEALTH_AI_DAILY_TOKENS_PER_USER", "2000000")))

    # --- Agents -------------------------------------------------------------------
    agent_max_steps: int = field(default_factory=lambda: int(_env("WEALTH_AI_AGENT_MAX_STEPS", "6")))

    # --- Risk thresholds ----------------------------------------------------------
    # Proposed transactions at or above this amount need a second approval from
    # compliance in addition to the advisor's confirmation.
    dual_approval_threshold: float = field(default_factory=lambda: float(_env("WEALTH_AI_DUAL_APPROVAL_CAD", "100000")))


settings = Settings()
