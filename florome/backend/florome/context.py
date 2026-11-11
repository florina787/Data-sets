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

    def __post_init__(self) -> None:
        if self.mcp is None:
            self.mcp = MCPGateway(self.settings)
