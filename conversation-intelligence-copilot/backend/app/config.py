"""Application configuration, read from environment variables (and an optional .env file).

Nothing secret is ever hardcoded. `GEMINI_API_KEY` is optional: without it the
copilot runs in deterministic mode and says so in every response.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Gemini -----------------------------------------------------------
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_model: str = "gemini-2.5-flash"
    gemini_max_output_tokens: int = 2048
    gemini_temperature: float = 0.1
    gemini_requests_per_minute: int = 10
    gemini_max_concurrency: int = 2
    gemini_max_retries: int = 3
    gemini_timeout_seconds: float = 45.0
    # Disable all model calls (deterministic mode) regardless of key presence.
    llm_enabled: bool = True
    # Rough USD per 1M tokens, for cost *estimates* only. Override for your tier.
    gemini_input_cost_per_mtok: float = 0.30
    gemini_output_cost_per_mtok: float = 2.50
    # Consecutive failures before the circuit opens, and how long it stays open.
    gemini_circuit_threshold: int = 3
    gemini_circuit_cooldown_seconds: float = 60.0

    # --- Embeddings / retrieval --------------------------------------------
    embedding_backend: Literal["auto", "sentence-transformers", "lsa"] = "auto"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunk_turns: int = 4
    chunk_overlap: int = 2

    # --- Paths ---------------------------------------------------------------
    raw_dataset_path: Path = PROJECT_ROOT / "data" / "raw" / "cs_conversations.csv.zip"
    synthetic_dataset_path: Path = PROJECT_ROOT / "data" / "synthetic" / "synthetic_conversations.csv"
    database_path: Path = PROJECT_ROOT / "data" / "processed" / "analytics.duckdb"
    memory_database_path: Path = PROJECT_ROOT / "data" / "processed" / "memory.sqlite"
    checkpoint_database_path: Path = PROJECT_ROOT / "data" / "processed" / "checkpoints.sqlite"
    faiss_index_path: Path = PROJECT_ROOT / "data" / "indexes" / "conversations.faiss"
    manifests_dir: Path = PROJECT_ROOT / "data" / "manifests"
    llm_cache_path: Path = PROJECT_ROOT / "data" / "processed" / "llm_cache.sqlite"

    # --- Behaviour -------------------------------------------------------------
    dataset_mode: Literal["original", "synthetic", "combined"] = "original"
    # Which message labels feed analytics: deterministic rules, or Gemini labels
    # (falling back to rules, with the method recorded, where Gemini has no label).
    label_source: Literal["rules", "gemini"] = "rules"
    labels_database_path: Path = PROJECT_ROOT / "data" / "processed" / "labels.sqlite"
    enable_synthetic_demo: bool = False
    session_retention_days: int = 30
    max_history_turns: int = 6
    min_agent_conversations: int = 3
    enable_langsmith: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080"]

    @property
    def gemini_configured(self) -> bool:
        return bool(self.llm_enabled and self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
