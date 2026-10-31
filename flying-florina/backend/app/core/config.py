"""Runtime configuration read from environment variables.

All defaults are the safe, offline, synthetic demo configuration. Nothing here
requires an account, an API key or network access.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent
FIXTURES_DIR = REPO_ROOT / "fixtures"
GENERATED_DIR = REPO_ROOT / "generated_adapters"
MCP_SERVERS_DIR = REPO_ROOT / "mcp_servers"

SEED = 20261024
APP_VERSION = "0.1.0"


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _llm_mode() -> str:
    raw = os.environ.get("LLM_ENABLED", "auto").strip().lower()
    if raw in {"0", "false", "no", "off", "none"}:
        return "off"
    if raw in {"1", "true", "yes", "on"}:
        return "on"
    return "auto"


def _secret(data_dir: Path) -> str:
    """Session-signing secret: env var, else a random value kept in the local data dir.

    The secret never leaves the machine and is not committed (data/ is git-ignored).
    """
    env = os.environ.get("FF_SESSION_SECRET")
    if env:
        return env
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / ".session_secret"
    if path.exists():
        return path.read_text().strip()
    value = secrets.token_hex(32)
    path.write_text(value)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return value


@dataclass
class Settings:
    demo_mode: bool = field(default_factory=lambda: _flag("DEMO_MODE", True))
    offline_mode: bool = field(default_factory=lambda: _flag("OFFLINE_MODE", True))
    # Local Qwen inference. "auto" (default): use the user's existing local Qwen model when it is found,
    # otherwise run the deterministic engine and say so. "on": same, but report Qwen missing as an error.
    # "off": never call a model. There is never an external or paid fallback.
    llm_mode: str = field(default_factory=lambda: _llm_mode())
    llm_url: str = field(default_factory=lambda: os.environ.get("LLM_URL", "http://127.0.0.1:11434"))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", ""))
    qwen_model_path: str = field(default_factory=lambda: os.environ.get("FF_QWEN_MODEL_PATH", ""))
    qwen_base_url: str = field(default_factory=lambda: os.environ.get("FF_QWEN_BASE_URL", ""))
    qwen_runtime: str = field(default_factory=lambda: os.environ.get("FF_QWEN_RUNTIME", "auto"))
    qwen_n_ctx: int = field(default_factory=lambda: int(os.environ.get("FF_QWEN_N_CTX", "4096")))
    qwen_threads: int = field(default_factory=lambda: int(os.environ.get("FF_QWEN_THREADS", str(max(1, (os.cpu_count() or 4) - 1)))))
    qwen_gpu_layers: int = field(default_factory=lambda: int(os.environ.get("FF_QWEN_GPU_LAYERS", "-1")))
    qwen_max_output_tokens: int = field(default_factory=lambda: int(os.environ.get("FF_QWEN_MAX_TOKENS", "320")))
    qwen_timeout_s: float = field(default_factory=lambda: float(os.environ.get("FF_QWEN_TIMEOUT_S", "45")))
    qwen_concurrency: int = field(default_factory=lambda: int(os.environ.get("FF_QWEN_CONCURRENCY", "1")))
    qwen_preload: bool = field(default_factory=lambda: _flag("FF_QWEN_PRELOAD", True))

    @property
    def llm_enabled(self) -> bool:
        return self.llm_mode != "off"
    brand_assets_authorized: bool = field(default_factory=lambda: _flag("BRAND_ASSETS_AUTHORIZED", False))
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("FF_DATA_DIR", str(BACKEND_DIR / "data"))))
    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.environ.get(
                "FF_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173"
            ).split(",")
            if o.strip()
        ]
    )
    max_upload_bytes: int = field(default_factory=lambda: int(os.environ.get("FF_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))))
    session_ttl_seconds: int = 8 * 3600
    approval_ttl_seconds: int = field(default_factory=lambda: int(os.environ.get("FF_APPROVAL_TTL_SECONDS", str(4 * 3600))))
    workflow_step_timeout_s: float = 20.0
    max_concurrent_workflows: int = 8

    generated_dir: Path = field(default_factory=lambda: Path(os.environ.get("FF_GENERATED_DIR", str(GENERATED_DIR))))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "flying_florina.db"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def session_secret(self) -> str:
        return _secret(self.data_dir)


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Used by tests to re-read the environment."""
    global _settings
    _settings = None
