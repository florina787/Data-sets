"""Runtime configuration. All values come from environment variables; secrets stay server-side."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "demo"))  # demo | production
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'var' / 'beauty_ai.db'}"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", str(ROOT / "data"))))
    storage_dir: Path = field(default_factory=lambda: Path(os.getenv("STORAGE_DIR", str(ROOT / "var" / "storage"))))
    policy_dir: Path = field(default_factory=lambda: Path(os.getenv("POLICY_DIR", str(ROOT / "policies"))))
    eval_config_dir: Path = field(default_factory=lambda: Path(os.getenv("EVAL_CONFIG_DIR", str(ROOT / "evaluation" / "configs"))))
    # Language generation mode: deterministic (default) | live
    llm_mode: str = field(default_factory=lambda: os.getenv("LLM_MODE", "deterministic"))
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "anthropic"))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "claude-opus-5-5"))
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY") or None)
    llm_timeout_s: float = field(default_factory=lambda: float(os.getenv("LLM_TIMEOUT_S", "30")))
    llm_max_output_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "800")))
    llm_token_budget_per_change: int = field(default_factory=lambda: int(os.getenv("LLM_TOKEN_BUDGET_PER_CHANGE", "60000")))
    # Beauty prediction mode: synthetic_fixture (default) | real (requires an authorized model adapter; unconfigured)
    prediction_mode: str = field(default_factory=lambda: os.getenv("PREDICTION_MODE", "synthetic_fixture"))
    # Deployment mode: simulated (default) | real (unconfigured; external writes disabled)
    deployment_mode: str = field(default_factory=lambda: os.getenv("DEPLOYMENT_MODE", "simulated"))
    # Evaluation job execution: background (thread pool) | inline (tests)
    eval_execution: str = field(default_factory=lambda: os.getenv("EVAL_EXECUTION", "background"))
    approval_ttl_hours: int = field(default_factory=lambda: int(os.getenv("APPROVAL_TTL_HOURS", "72")))
    evaluation_max_age_days: int = field(default_factory=lambda: int(os.getenv("EVALUATION_MAX_AGE_DAYS", "14")))
    image_sandbox_enabled: bool = field(default_factory=lambda: _bool("IMAGE_SANDBOX_ENABLED", False))
    cors_origins: str = field(default_factory=lambda: os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"))

    @property
    def production(self) -> bool:
        return self.app_env == "production"

    @property
    def demo(self) -> bool:
        return not self.production

    @property
    def persona_selector_enabled(self) -> bool:
        return self.demo

    def modes(self) -> dict:
        live_ready = self.llm_mode == "live" and bool(self.anthropic_api_key)
        return {
            "app_env": self.app_env,
            "language_generation": {
                "mode": "live" if live_ready else "deterministic",
                "requested": self.llm_mode,
                "provider": self.llm_provider if live_ready else None,
                "model": self.llm_model if live_ready else None,
                "status": "configured" if live_ready else ("unconfigured: LLM_MODE=live but no API key" if self.llm_mode == "live" else "deterministic templates (no model calls)"),
            },
            "beauty_prediction": {
                "mode": self.prediction_mode,
                "status": "synthetic fixture adapter — predictions are fixed-seed fixtures, not computer-vision inference"
                if self.prediction_mode == "synthetic_fixture" else "unconfigured: no authorized real model adapter supplied",
            },
            "deployment": {
                "mode": self.deployment_mode,
                "status": "simulated release executor — no real traffic, no external writes"
                if self.deployment_mode == "simulated" else "unconfigured: real deployment adapter not supplied; external writes disabled",
            },
            "retrieval": {"mode": "lexical (BM25, offline)", "embeddings": "unconfigured"},
            "persona_selector": "enabled (demo only)" if self.persona_selector_enabled else "disabled (production mode)",
            "image_sandbox": "enabled" if self.image_sandbox_enabled else "disabled",
        }


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    global _settings
    _settings = None
