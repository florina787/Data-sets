"""End-to-end MCP test: launches the generated MCP server over stdio and calls the tool."""
import asyncio
import os
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from adapter.auth import issue_demo_token

ROOT = Path(__file__).resolve().parents[1]


async def _call(token: str, part: str):
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server.server"], cwd=str(ROOT),
                                   env={"PYTHONPATH": str(ROOT), "MCP_ADAPTER_TOKEN": token, "PATH": os.environ.get("PATH", ""),
                                        "ADAPTER_DEMO_SECRET": os.environ["ADAPTER_DEMO_SECRET"]})
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            result = await session.call_tool("get_part_availability", {"part_number": part})
            return names, result


def _payload(result):
    if getattr(result, "structured_content", None):
        return result.structured_content
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    import json
    return json.loads(result.content[0].text)


def test_mcp_tool_listed_and_returns_availability():
    names, result = asyncio.run(_call(issue_demo_token("agent", ["inventory.read"]), "P-7731"))
    assert names == ["get_part_availability"]
    payload = _payload(result)
    payload = payload.get("result", payload)
    assert payload["part_number"] == "P-7731"


def test_mcp_tool_denies_without_scope():
    _, result = asyncio.run(_call(issue_demo_token("agent", ["workorder.write"]), "P-7731"))
    payload = _payload(result)
    payload = payload.get("result", payload)
    assert payload == {"error": "insufficient_scope"}
