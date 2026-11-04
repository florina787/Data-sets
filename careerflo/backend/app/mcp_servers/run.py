"""Run one Career_flo MCP server over stdio for external MCP clients.

    python -m app.mcp_servers.run jobs

User-scoped tools take ``user_id``; only expose them to clients you trust with that user's data.
"""
from __future__ import annotations

import sys

from ..mcp_gateway import SERVERS

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in SERVERS:
        sys.exit(f"usage: python -m app.mcp_servers.run [{'|'.join(SERVERS)}]")
    SERVERS[name][0].run("stdio")
