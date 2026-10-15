"""Runtime configuration. Every value comes from the environment (see .env.example).

Defaults are chosen for a local, single-machine demo and are recorded in docs/DECISIONS.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _load_env_file() -> None:
    """Load KEY=VALUE pairs from FLOPILOT_ENV_FILE (default ../.env, then ./.env) without overriding
    variables that are already set. Keeps local runs dependency-free; Docker passes env directly."""
    candidates = [os.getenv("FLOPILOT_ENV_FILE")] if os.getenv("FLOPILOT_ENV_FILE") else [
        str(Path(__file__).resolve().parents[2] / ".env"), ".env"]
    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        break


if not os.getenv("PYTEST_CURRENT_TEST") and os.getenv("FLOPILOT_SKIP_ENV_FILE") != "1":
    _load_env_file()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "FloPilot"
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("FLOPILOT_DATA_DIR", "./data")).resolve())
    database_url: str = os.getenv("FLOPILOT_DATABASE_URL", "")  # empty -> sqlite file under data_dir

    # Upload / workbook limits (realistic initial limits for an in-memory openpyxl pipeline)
    max_upload_mb: int = _int("FLOPILOT_MAX_UPLOAD_MB", 10)
    max_cells: int = _int("FLOPILOT_MAX_CELLS", 500_000)
    max_sheets: int = _int("FLOPILOT_MAX_SHEETS", 50)
    max_uncompressed_mb: int = _int("FLOPILOT_MAX_UNCOMPRESSED_MB", 150)

    # Per-user request limits (per minute)
    chat_rate_per_min: int = _int("FLOPILOT_CHAT_RATE_PER_MIN", 30)
    upload_rate_per_min: int = _int("FLOPILOT_UPLOAD_RATE_PER_MIN", 20)

    # Auth
    auth_mode: str = os.getenv("FLOPILOT_AUTH_MODE", "demo")  # demo | oidc (interface only)
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("FLOPILOT_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080").split(",") if o.strip()
    )

    # LLM
    llm_provider: str = os.getenv("FLOPILOT_LLM_PROVIDER", "demo")  # demo | anthropic
    llm_model: str = os.getenv("FLOPILOT_LLM_MODEL", "claude-opus-5-5")
    llm_effort: str = os.getenv("FLOPILOT_LLM_EFFORT", "medium")
    llm_input_cost_per_mtok: float = _float("FLOPILOT_LLM_INPUT_COST_PER_MTOK", 4.0)
    llm_output_cost_per_mtok: float = _float("FLOPILOT_LLM_OUTPUT_COST_PER_MTOK", 20.0)

    # Harness budgets
    max_steps: int = _int("FLOPILOT_MAX_STEPS", 8)
    max_tokens_per_run: int = _int("FLOPILOT_MAX_TOKENS_PER_RUN", 60_000)
    max_cost_per_run_usd: float = _float("FLOPILOT_MAX_COST_PER_RUN_USD", 0.50)
    tool_timeout_s: float = _float("FLOPILOT_TOOL_TIMEOUT_S", 30.0)
    max_tool_rows: int = _int("FLOPILOT_MAX_TOOL_ROWS", 50)

    # Recalculation engine (LibreOffice headless) used only to *verify* formulas
    recalc_engine: str = os.getenv("FLOPILOT_RECALC_ENGINE", "auto")  # auto | libreoffice | none
    recalc_timeout_s: float = _float("FLOPILOT_RECALC_TIMEOUT_S", 60.0)

    # Retention
    retention_days: int = _int("FLOPILOT_RETENTION_DAYS", 30)
    log_workbook_content: bool = _bool("FLOPILOT_LOG_WORKBOOK_CONTENT", False)

    @property
    def sqlite_path(self) -> Path:
        return self.data_dir / "flopilot.db"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Used by tests after changing environment variables."""
    global _settings
    _settings = None
