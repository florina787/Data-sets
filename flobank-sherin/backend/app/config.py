"""Runtime settings. Every value can be overridden with an environment variable of the same name."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL in docker-compose; SQLite works for a zero-setup local run.
    database_url: str = f"sqlite:///{ROOT / 'var' / 'flobank.db'}"
    checkpoint_path: str = str(ROOT / "var" / "harness_checkpoints.sqlite")

    # "demo" seeds clearly labelled synthetic records. Real measurements (request latency, CPU, the
    # agent runs you trigger) are always recorded with data_class="measured" and never mixed in.
    app_mode: str = "demo"
    seed: int = 20261103
    demo_months: int = 14
    demo_end_month: str = "2026-10"  # last closed accounting month in the synthetic ledger

    # Optional local Qwen via Ollama. When unreachable, agents use deterministic tools only and say so.
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_timeout_s: float = 60.0
    llm_enabled: bool = True

    # Local inference cost model (no API bill, but compute and power are real costs).
    local_gpu_hourly_usd: float = 1.10        # amortised workstation GPU + host
    local_power_kw: float = 0.45
    electricity_usd_per_kwh: float = 0.16

    base_currency: str = "USD"
    cors_origins: str = "http://localhost:5173,http://localhost:8080"


@lru_cache
def get_settings() -> Settings:
    return Settings()
