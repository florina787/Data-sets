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

    # --- LLM provider ---------------------------------------------------------
    # auto = the local model (Qwen via llama.cpp) if it has been downloaded, else Gemini if GEMINI_API_KEY is set,
    # else deterministic mode. "none" forces deterministic mode.
    llm_provider: Literal["auto", "gemini", "local", "none"] = "auto"

    # Intent routing is confidence-aware for every provider (app/agents/intent_router.py): policy -> high-precision
    # rules -> calibrated semantic match -> model -> broad rules -> clarify.

    # --- Local LLM (llama.cpp, no key) -----------------------------------------
    local_model_repo: str = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    local_model_file: str = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    local_model_dir: Path = PROJECT_ROOT / "data" / "models"
    local_n_ctx: int = 8192
    local_threads: int = 4
    local_max_output_tokens: int = 600
    local_n_gpu_layers: int = -1  # -1 = offload every layer when the llama.cpp build supports a GPU; 0 = CPU only
    local_preload: bool = True  # load the local model in the background at API start-up, so the first question is warm
    # Time budget for model-written explanations; past it, the evidence-backed deterministic narrative is used.
    explanation_timeout_seconds: float = 20.0

    # --- Gemini -----------------------------------------------------------
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_model: str = "gemini-2.5-flash"
    # Route calls through Vertex AI (express mode, API key) instead of the Gemini Developer API.
    # Needed for Google Cloud keys (e.g. "AQ." keys) whose project has the Vertex AI API enabled.
    gemini_use_vertex: bool = False
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
    # hybrid = Reciprocal Rank Fusion of the dense (MiniLM) and LSA rankings; dense / lsa use one index only.
    retrieval_mode: Literal["hybrid", "dense", "lsa"] = "hybrid"
    rrf_k: int = 60
    # LSA's vote in hybrid fusion relative to MiniLM (1.0 = equal). See EVALUATION.md for how it was chosen.
    hybrid_lsa_weight: float = 0.15

    # --- Paths ---------------------------------------------------------------
    raw_dataset_path: Path = PROJECT_ROOT / "data" / "raw" / "cs_conversations.csv.zip"
    synthetic_dataset_path: Path = PROJECT_ROOT / "data" / "synthetic" / "synthetic_conversations.csv"
    database_path: Path = PROJECT_ROOT / "data" / "processed" / "analytics.duckdb"
    memory_database_path: Path = PROJECT_ROOT / "data" / "processed" / "memory.sqlite"
    checkpoint_backend: Literal["memory", "sqlite"] = "memory"  # sqlite persists every intermediate graph state (debugging)
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

    @property
    def resolved_llm_provider(self) -> str | None:
        if self.llm_provider == "local" or (self.llm_provider == "auto" and (self.local_model_dir / self.local_model_file).exists()):
            return "local"
        if self.llm_provider == "gemini" or (self.llm_provider == "auto" and self.gemini_api_key):
            return "gemini"
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
