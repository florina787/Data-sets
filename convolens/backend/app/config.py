"""Application settings. All secrets are read from the backend environment only."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"), extra="ignore")

    # Storage
    data_dir: Path = Field(default=BACKEND_DIR / "var")
    database_url: str | None = None  # defaults to sqlite in data_dir
    demo_data_dir: Path = Field(default=PROJECT_DIR / "data" / "demo")
    import_root: Path = Field(default=PROJECT_DIR / "data" / "imports")  # local-path imports must live under here
    max_upload_mb: int = 600

    # Sampling
    sample_size: int = 3000
    sample_seed: int = 20240601
    max_conversation_messages: int = 50

    # Model provider (connected analysis)
    model_provider: Literal["none", "anthropic", "bedrock", "gemini"] = "none"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    bedrock_model_id: str | None = None
    aws_region: str | None = None
    # Google Gemini via its OpenAI-compatible endpoint. The key may be set here (GOOGLE_API_KEY) or injected by an
    # egress proxy as an Authorization header (GEMINI_KEY_VIA_PROXY=true), in which case it never enters the process.
    google_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    gemini_key_via_proxy: bool = False
    gemini_reasoning_effort: str = "low"  # thinking budget; low keeps latency and free-tier usage down
    gemini_max_tokens: int = 8000
    model_requests_per_minute: float = 0  # 0 = unlimited; set for free-tier quotas
    model_max_tokens: int = 1500
    model_timeout_s: float = 60.0
    model_max_retries: int = 2

    # Retrieval
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings_enabled: bool = True
    # "local" = sentence-transformers on this machine; "gemini" = gemini-embedding-001 over the OpenAI-compatible
    # endpoint. Gemini vectors are cached in SQLite by text hash, so each message is embedded once, ever.
    embedding_provider: Literal["local", "gemini"] = "local"
    gemini_embedding_model: str = "gemini-embedding-001"
    gemini_embedding_dims: int = 768
    gemini_embedding_batch: int = 90  # free tier: 100 texts per minute
    gemini_embedding_max_requests: int = 50  # texts embedded per process at query time; protects the free-tier quota

    # LangSmith
    langsmith_tracing: bool = False
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str = "convolens"
    langsmith_endpoint: str | None = None
    langsmith_send_raw: bool = False  # never send unredacted content unless explicitly enabled

    # Flo limits
    flo_max_tool_calls: int = 8
    flo_max_iterations: int = 3
    flo_max_tokens_per_request: int = 24000
    flo_timeout_s: float = 90.0
    flo_min_denominator: int = 5
    min_group_size: int = 20

    # HTTP
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'convolens.db'}"

    @property
    def checkpoint_path(self) -> Path:
        return self.data_dir / "checkpoints.db"

    @property
    def model_configured(self) -> bool:
        if self.model_provider == "anthropic":
            return bool(self.anthropic_api_key and self.anthropic_api_key.get_secret_value())
        if self.model_provider == "bedrock":
            return bool(self.bedrock_model_id and self.aws_region)
        if self.model_provider == "gemini":
            return bool(self.gemini_key_via_proxy or (self.google_api_key and self.google_api_key.get_secret_value()))
        return False

    @property
    def model_id(self) -> str | None:
        if self.model_provider == "anthropic":
            return self.anthropic_model
        if self.model_provider == "bedrock":
            return self.bedrock_model_id
        if self.model_provider == "gemini":
            return self.gemini_model
        return None

    @property
    def langsmith_configured(self) -> bool:
        return bool(self.langsmith_tracing and self.langsmith_api_key and self.langsmith_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.import_root.mkdir(parents=True, exist_ok=True)
    return s
