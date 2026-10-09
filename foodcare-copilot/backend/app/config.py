"""Platform settings. Everything has a local, key-free default (DEMO mode)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"


@dataclass(frozen=True)
class Settings:
    var_dir: Path = field(default_factory=lambda: Path(os.environ.get("FOODCARE_VAR_DIR", ROOT / "var")).resolve())
    api_host: str = "127.0.0.1"
    api_port: int = int(os.environ.get("FOODCARE_API_PORT", "8700"))
    storefront_port: int = int(os.environ.get("FOODCARE_STOREFRONT_PORT", "8801"))
    demo_clock: str = os.environ.get("FOODCARE_DEMO_CLOCK", "2026-10-31T12:00:00-04:00")
    default_mode: str = os.environ.get("FOODCARE_MODE", "demo")
    anthropic_api_key: str | None = os.environ.get("ANTHROPIC_API_KEY") or None
    anthropic_model: str | None = os.environ.get("ANTHROPIC_MODEL") or None
    llm_max_tokens: int = int(os.environ.get("FOODCARE_LLM_MAX_TOKENS", "4000"))
    llm_max_calls_per_run: int = int(os.environ.get("FOODCARE_LLM_MAX_CALLS_PER_RUN", "6"))
    llm_timeout_s: float = float(os.environ.get("FOODCARE_LLM_TIMEOUT_S", "60"))
    tool_timeout_s: int = int(os.environ.get("FOODCARE_TOOL_TIMEOUT_S", "180"))
    tool_output_limit: int = 200_000
    max_repair_attempts: int = 1
    fault_delay_s: float = float(os.environ.get("FOODCARE_FAULT_DELAY_S", "4"))
    session_hours: int = 12

    def __post_init__(self) -> None:
        # Absolute paths only: child processes run from their own release directories.
        object.__setattr__(self, "var_dir", Path(self.var_dir).resolve())

    @property
    def db_path(self) -> Path:
        return self.var_dir / "platform.db"

    @property
    def checkpoint_path(self) -> Path:
        return self.var_dir / "checkpoints.db"

    @property
    def storefront_repo(self) -> Path:
        return self.var_dir / "storefront-repo"

    @property
    def workspaces_dir(self) -> Path:
        return self.var_dir / "workspaces"

    @property
    def releases_dir(self) -> Path:
        return self.var_dir / "releases"

    @property
    def test_runs_dir(self) -> Path:
        return self.var_dir / "test-runs"

    @property
    def run_dir(self) -> Path:
        return self.var_dir / "run"

    @property
    def telemetry_file(self) -> Path:
        return self.var_dir / "telemetry" / "storefront.jsonl"

    @property
    def commerce_db(self) -> Path:
        return self.var_dir / "storefront-data" / "commerce.db"

    @property
    def storefront_static(self) -> Path:
        return ROOT / "apps" / "storefront" / "dist"

    @property
    def control_room_static(self) -> Path:
        return ROOT / "apps" / "control-room" / "dist"

    @property
    def inventory_url(self) -> str:
        return f"http://{self.api_host}:{self.api_port}/sim/inventory"

    @property
    def storefront_url(self) -> str:
        return f"http://{self.api_host}:{self.storefront_port}"

    @property
    def live_available(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_model)


_settings = Settings()


def get_settings() -> Settings:
    return _settings


def configure(**overrides) -> Settings:
    """Replace settings (used by tests and scripts)."""
    global _settings
    _settings = replace(_settings, **overrides)
    return _settings
