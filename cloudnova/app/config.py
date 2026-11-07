"""Configuration from environment (+ optional .env). Business constants live here and in pipeline/rules.py only."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.split("#", 1)[0].strip()
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    raw_csv: Path
    data_dir: Path
    runtime_dir: Path
    fx_to_usd: dict = field(default_factory=dict)
    fx_direction: str = "documented"
    llm_provider: str = "qwen"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    llm_model: str = "qwen2.5-coder:3b"
    llm_timeout_s: float = 90.0
    llm_max_tokens: int = 512
    max_result_rows: int = 200
    query_timeout_s: float = 10.0
    duckdb_memory_limit: str = "1GB"
    allow_pii: bool = False
    query_mode: str = "hybrid"     # hybrid = approved metrics first, Qwen SQL fallback · llm = Qwen SQL for every data question
    llm_start_cmd: str = ""
    llm_start_timeout_s: float = 120.0
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def db_path(self) -> Path:
        return self.data_dir / "cloudnova.duckdb"


def _path(name: str, default: str) -> Path:
    p = Path(_env(name, default))
    return p if p.is_absolute() else ROOT / p


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    direction = _env("FX_DIRECTION", "documented")
    if direction not in ("documented", "inverse"):
        raise ValueError("FX_DIRECTION must be 'documented' or 'inverse'")
    return Settings(
        raw_csv=_path("CLOUDNOVA_RAW_CSV", "data/raw/cloudnova_invoices.csv"),
        data_dir=_path("CLOUDNOVA_DATA_DIR", "data/processed"),
        runtime_dir=_path("CLOUDNOVA_RUNTIME_DIR", "data/runtime"),
        fx_to_usd={"USD": 1.0, "EUR": float(_env("FX_EUR_USD", "1.08")), "GBP": float(_env("FX_GBP_USD", "1.27"))},
        fx_direction=direction,
        llm_provider=_env("LLM_PROVIDER", "qwen"),
        llm_base_url=_env("LLM_BASE_URL", "http://127.0.0.1:11434/v1").rstrip("/"),
        llm_model=_env("LLM_MODEL", "qwen2.5-coder:3b"),
        llm_timeout_s=float(_env("LLM_TIMEOUT_S", "90")),
        llm_max_tokens=int(_env("LLM_MAX_TOKENS", "512")),
        max_result_rows=int(_env("MAX_RESULT_ROWS", "200")),
        query_timeout_s=float(_env("QUERY_TIMEOUT_S", "10")),
        duckdb_memory_limit=_env("DUCKDB_MEMORY_LIMIT", "1GB"),
        allow_pii=_env("ALLOW_PII", "false").lower() in ("1", "true", "yes"),
        query_mode=_env("QUERY_MODE", "hybrid"),
        llm_start_cmd=_env("LLM_START_CMD", ""),
        llm_start_timeout_s=float(_env("LLM_START_TIMEOUT_S", "120")),
        host=_env("CLOUDNOVA_HOST", "127.0.0.1"),
        port=int(_env("CLOUDNOVA_PORT", "8000")),
    )
