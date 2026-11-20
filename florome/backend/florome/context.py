"""Process-wide application context (settings, connector registry, MCP gateway)."""

from __future__ import annotations

from dataclasses import dataclass, field

from florome.config import Settings
from florome.connectors.registry import ConnectorRegistry
from florome.mcp.gateway import MCPGateway


@dataclass
class AppContext:
    settings: Settings
    registry: ConnectorRegistry = field(default_factory=ConnectorRegistry)
    mcp: MCPGateway | None = None
    demo_tokens: dict[str, str] = field(default_factory=dict)  # token -> user id (demo mode only)

    signing_key: bytes = b""

    def __post_init__(self) -> None:
        if self.mcp is None:
            self.mcp = MCPGateway(self.settings)
        if not self.signing_key:
            import secrets

            key = self.settings.signing_key
            # Production must set FLOROME_SIGNING_KEY; demo uses an ephemeral key (plans do not survive a restart).
            self.signing_key = key.get_secret_value().encode() if key else secrets.token_bytes(32)

    def sign(self, *parts: str) -> str:
        import hashlib
        import hmac

        return hmac.new(self.signing_key, "|".join(parts).encode(), hashlib.sha256).hexdigest()
