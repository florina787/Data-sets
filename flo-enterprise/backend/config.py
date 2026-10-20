"""Runtime configuration. Every external dependency has an explicit mock/local fallback."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: _env("FLO_ENV", "development"))
    database_url: str = field(default_factory=lambda: _env("FLO_DATABASE_URL", f"sqlite:///{ROOT / 'var' / 'flo.db'}"))
    redis_url: str = field(default_factory=lambda: _env("FLO_REDIS_URL", ""))
    checkpoint_db: str = field(default_factory=lambda: _env("FLO_CHECKPOINT_DB", str(ROOT / "var" / "checkpoints.sqlite")))
    # Demo signing key for the mock identity provider. Production uses the enterprise IdP (OIDC) and never this key.
    jwt_secret: str = field(default_factory=lambda: _env("FLO_JWT_SECRET", "dev-only-insecure-signing-key-change-me"))
    jwt_ttl_seconds: int = field(default_factory=lambda: int(_env("FLO_JWT_TTL_SECONDS", "1800")))
    # Key-encryption key for the token vault. Production: secret manager / KMS.
    vault_key: str = field(default_factory=lambda: _env("FLO_VAULT_KEY", ""))
    model_provider: str = field(default_factory=lambda: _env("FLO_MODEL_PROVIDER", "mock"))
    bedrock_region: str = field(default_factory=lambda: _env("FLO_BEDROCK_REGION", "ca-central-1"))
    langsmith_api_key: str = field(default_factory=lambda: _env("LANGSMITH_API_KEY", ""))
    langsmith_project: str = field(default_factory=lambda: _env("LANGSMITH_PROJECT", "flo-enterprise"))
    opa_url: str = field(default_factory=lambda: _env("FLO_OPA_URL", ""))
    max_concurrent_workflows: int = field(default_factory=lambda: int(_env("FLO_MAX_CONCURRENT_WORKFLOWS", "32")))
    max_input_chars: int = field(default_factory=lambda: int(_env("FLO_MAX_INPUT_CHARS", "4000")))
    cors_origins: str = field(default_factory=lambda: _env("FLO_CORS_ORIGINS", "http://localhost:5173,http://localhost:8080"))
    export_dir: str = field(default_factory=lambda: _env("FLO_EXPORT_DIR", str(ROOT / "var" / "exports")))

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_production and s.jwt_secret.startswith("dev-only"):
        raise RuntimeError("FLO_JWT_SECRET must be set in production")
    if s.is_production and not s.vault_key:
        raise RuntimeError("FLO_VAULT_KEY must be set in production")
    return s
