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

    # ---- Florome Shield
    shield_tools_dir: str = str(PACKAGE_DIR.parent / ".tools" / "bin")  # opengrep, trivy, opa (scripts/fetch_shield_tools.sh)
    shield_authorized_roots: list[str] = Field(default_factory=lambda: [str(PACKAGE_DIR / "shield" / "range" / "targets")])
    shield_require_network_namespace: bool = True  # verification refuses to run without `unshare -n`
    shield_opa_mode: Literal["required", "optional", "off"] = "optional"  # optional: use OPA if installed; errors fail closed
    shield_scan_quota_per_hour: int = 30
    shield_verify_quota_per_hour: int = 120
    shield_tool_timeout_seconds: float = 180.0
    shield_probe_timeout_seconds: float = 30.0
    signing_key: SecretStr | None = None  # HMAC key for plan signatures; an ephemeral key is generated when unset (demo)
    rate_limit_per_minute: int = 240  # mutating requests per principal
    # Conversation Intelligence Copilot (Project A), called over HTTP. Empty string disables the integration.
    copilot_url: str = "http://127.0.0.1:8001"
    copilot_timeout_seconds: float = 60.0

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
