"""Connects to the local demo MCP server over stdio, discovers tools and checks pins."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any

import yaml

from app.core.config import FIXTURES_DIR, REPO_ROOT, get_settings
from app.core.security import Actor, issue_token
from app.core.util import sha256_json

PINS = FIXTURES_DIR / "policies" / "mcp_allowlist.yaml"


def _schema(tool: Any) -> dict[str, Any]:
    return getattr(tool, "input_schema", None) or getattr(tool, "inputSchema", None) or {}


async def _session(token: str, calls: list[tuple[str, dict[str, Any]]]) -> dict[str, Any]:
    from mcp import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    env = {"PATH": os.environ.get("PATH", ""), "FF_MCP_TOKEN": token, "FF_DATA_DIR": str(get_settings().data_dir),
           "FF_SESSION_SECRET": get_settings().session_secret, "OFFLINE_MODE": "true"}
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_servers.demo_maintenance.server"], cwd=str(REPO_ROOT), env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            results = []
            for name, args in calls:
                r = await session.call_tool(name, args)
                payload = getattr(r, "structured_content", None) or getattr(r, "structuredContent", None)
                if payload is None and r.content:
                    text = getattr(r.content[0], "text", "")
                    try:
                        payload = json.loads(text)
                    except ValueError:
                        payload = {"text": text}
                results.append({"tool": name, "args": args, "result": payload})
            return {"tools": [{"name": t.name, "description": t.description, "schema_sha256": sha256_json(_schema(t))} for t in listed.tools], "calls": results}


def discover_demo_server(actor: Actor, timeout_s: float = 30.0) -> dict[str, Any]:
    pins = {p["name"]: p for p in (yaml.safe_load(PINS.read_text()) or {}).get("tools", [])}
    token = issue_token(actor.id, audience="ff-mcp-demo")
    try:
        out = asyncio.run(asyncio.wait_for(_session(token, [("get_fleet_overview", {}), ("get_part_availability", {"part_number": "P-7731"})]), timeout_s))
    except Exception as err:  # noqa: BLE001
        return {"connected": False, "error": f"{type(err).__name__}: {err}", "tools": [], "calls": []}
    for t in out["tools"]:
        pin = pins.get(t["name"])
        t["allowlisted"] = pin is not None
        t["pin_ok"] = bool(pin and pin["schema_sha256"] == t["schema_sha256"])
        t["status"] = "trusted" if t["pin_ok"] else "untrusted - not callable"
    trusted = {t["name"] for t in out["tools"] if t["pin_ok"]}
    out["calls"] = [c if c["tool"] in trusted else {**c, "result": "not called: tool not pinned"} for c in out["calls"]]
    return {"connected": True, "transport": "stdio", "server": "mcp_servers/demo_maintenance", **out}
