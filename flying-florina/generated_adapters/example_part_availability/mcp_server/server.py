"""MCP server exposing one read-only tool over the adapter (official Python SDK).

Run:  python -m mcp_server.server   (stdio transport)
MCP is the agent interface only. Authorization: the server requires a token
with audience ff-parts-adapter and scope inventory.read, supplied via the
MCP_ADAPTER_TOKEN environment variable at launch, and checks it on every call.
"""
import os
import re

from mcp.server.mcpserver import MCPServer

from adapter import backend
from adapter.auth import AuthError, verify

PART_RE = re.compile(r"^P-[0-9A-Z]{3,8}$")
server = MCPServer(name="ff-part-availability", version="1.0.0",
                   instructions="Read-only, synthetic part availability. No write tools exist.")


@server.tool(name="get_part_availability", description="Verified, read-only availability for one part number (synthetic data).")
def get_part_availability(part_number: str) -> dict:
    try:
        verify("Bearer " + os.environ.get("MCP_ADAPTER_TOKEN", ""))
    except AuthError as err:
        return {"error": err.code}
    if not PART_RE.fullmatch(part_number):
        return {"error": "invalid_part_number"}
    result = backend.get_part_availability(part_number)
    return result.model_dump(mode="json") if result else {"error": "not_found"}


if __name__ == "__main__":
    server.run("stdio")
