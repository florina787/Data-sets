"""Runtime settings. Secrets are read from the environment and never returned by any API."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_MCP_SERVERS = {
    # name -> module path. Only bundled, reviewed servers are allow-listed by default.
    "sandbox-ops": "florome.mcp_servers.sandbox_ops_server",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLOROME_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./florome.db"
    # demo: synthetic tenant, sandbox connector, demo bearer tokens. live: only verified connectors; no demo tokens.
    default_mode: Literal["demo", "live"] = "demo"
    enable_demo_tokens: bool = True
    # Extra allow-listed MCP server commands, as "name=module.path" entries (python -m module).
    mcp_allowlist_extra: list[str] = Field(default_factory=list)
    mcp_call_timeout_seconds: float = 15.0
    action_timeout_seconds: float = 30.0
    action_max_attempts: int = 3
    # GitHub REST connector (read + issue creation). Optional; never sent to any model.
    github_token: SecretStr | None = None
    github_repository: str | None = None  # "owner/name"
    github_api_url: str = "https://api.github.com"

    def mcp_allowlist(self) -> dict[str, list[str]]:
        """name -> argv for allow-listed stdio servers. Commands are fixed here, never taken from API input."""
        allowed = {name: [sys.executable, "-m", mod] for name, mod in BUNDLED_MCP_SERVERS.items()}
        for entry in self.mcp_allowlist_extra:
            name, _, mod = entry.partition("=")
            if name and mod:
                allowed[name.strip()] = [sys.executable, "-m", mod.strip()]
        return allowed


@lru_cache
def get_settings() -> Settings:
    return Settings()
