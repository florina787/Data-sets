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
    # Local LLM: an OpenAI-compatible server that is already running on this machine
    # (Ollama, LM Studio, llama.cpp llama-server, MLX). Nothing is downloaded or started.
    llm_base_url: str | None = (os.environ.get("FOODCARE_LLM_BASE_URL") or "").rstrip("/") or None
    llm_model: str | None = os.environ.get("FOODCARE_LLM_MODEL") or None
    llm_api_key: str | None = os.environ.get("FOODCARE_LLM_API_KEY") or None
    llm_response_format: str = os.environ.get("FOODCARE_LLM_RESPONSE_FORMAT", "json_schema")
    llm_max_tokens: int = int(os.environ.get("FOODCARE_LLM_MAX_TOKENS", "800"))
    llm_max_prompt_chars: int = int(os.environ.get("FOODCARE_LLM_MAX_PROMPT_CHARS", "6000"))
    llm_max_calls_per_run: int = int(os.environ.get("FOODCARE_LLM_MAX_CALLS_PER_RUN", "6"))
    llm_timeout_s: float = float(os.environ.get("FOODCARE_LLM_TIMEOUT_S", "60"))
    llm_concurrency: int = int(os.environ.get("FOODCARE_LLM_CONCURRENCY", "1"))
    llm_queue_size: int = int(os.environ.get("FOODCARE_LLM_QUEUE_SIZE", "4"))
    llm_queue_wait_s: float = float(os.environ.get("FOODCARE_LLM_QUEUE_WAIT_S", "20"))
    llm_cache_entries: int = int(os.environ.get("FOODCARE_LLM_CACHE_ENTRIES", "64"))
    memory_backend: str = os.environ.get("FOODCARE_MEMORY_BACKEND", "sqlite")
    memory_retention_days: int = int(os.environ.get("FOODCARE_MEMORY_RETENTION_DAYS", "180"))
    memory_backups_kept: int = int(os.environ.get("FOODCARE_MEMORY_BACKUPS_KEPT", "5"))
    memory_backup_interval_h: float = float(os.environ.get("FOODCARE_MEMORY_BACKUP_INTERVAL_H", "24"))
    memory_context_turns: int = int(os.environ.get("FOODCARE_MEMORY_CONTEXT_TURNS", "3"))
    memory_summary_after: int = int(os.environ.get("FOODCARE_MEMORY_SUMMARY_AFTER", "20"))
    vision_concurrency: int = int(os.environ.get("FOODCARE_VISION_CONCURRENCY", "1"))
    vision_queue_size: int = int(os.environ.get("FOODCARE_VISION_QUEUE_SIZE", "2"))
    vision_queue_wait_s: float = float(os.environ.get("FOODCARE_VISION_QUEUE_WAIT_S", "30"))
    vision_max_upload_mb: float = float(os.environ.get("FOODCARE_VISION_MAX_UPLOAD_MB", "15"))
    vision_max_pixels: int = int(os.environ.get("FOODCARE_VISION_MAX_PIXELS", "40000000"))
    vision_working_px: int = int(os.environ.get("FOODCARE_VISION_WORKING_PX", "1024"))
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
    def memory_dir(self) -> Path:
        """Conversation memory and execution history. Kept across "Reset Demo"."""
        return self.var_dir / "memory"

    @property
    def memory_db_path(self) -> Path:
        return self.memory_dir / "memory.db"

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
        return bool(self.llm_base_url and self.llm_model)


_settings = Settings()


def get_settings() -> Settings:
    return _settings


def configure(**overrides) -> Settings:
    """Replace settings (used by tests and scripts)."""
    global _settings
    _settings = replace(_settings, **overrides)
    return _settings
