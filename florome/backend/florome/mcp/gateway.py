"""MCP Gateway: the only path by which Florome talks to MCP servers.

Controls, in the order they apply
---------------------------------
1. Allow-list. A server can be registered only by a name present in the server-side allow-list; the command that
   starts it comes from that list, never from API input. Servers run with a minimal environment (no inherited
   credentials).
2. Discovery review. Tool descriptions and schemas are untrusted. They are sanitised (control/bidi characters
   stripped, length-bounded) and screened for prompt-injection. Flagged tools are quarantined.
3. Default-deny enablement. A newly discovered tool is enabled automatically only if it comes from a bundled,
   reviewed server, declares itself read-only and is not flagged. Everything else waits for an admin, whose
   enablement pins the schema hash.
4. Schema pinning. On every invocation the live schema is compared with the pinned hash; drift ("rug pull")
   disables the tool and denies the call.
5. Read-only invocation. The gateway invokes read tools only. Write tools are never invoked directly; they would
   have to run through an approved remediation plan (not yet wired for MCP: see docs/MCP_ARCHITECTURE.md).
   ``read_only_hint`` is a claim by the server, which is why step 3 requires admin review for non-bundled servers.
6. Argument validation against the pinned JSON schema, a call timeout, and output sanitisation (credential and PII
   redaction, injection flags, size bound). Every step is audited.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import jsonschema
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.config import BUNDLED_MCP_SERVERS, PACKAGE_DIR, Settings
from florome.models import MCPServerRecord, MCPToolRecord, utcnow
from florome.security import audit
from florome.security.injection import sanitize, scan
from florome.security.rbac import Principal
from florome.security.redaction import redact

MAX_OUTPUT_CHARS = 20_000


class MCPGatewayError(RuntimeError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _schema_hash(name: str, schema: dict[str, Any]) -> str:
    return audit.sha256({"name": name, "schema": schema})


class MCPGateway:
    def __init__(self, settings: Settings):
        self.settings = settings

    # ------------------------------------------------------------------------------------------- transport

    def _params(self, name: str) -> StdioServerParameters:
        argv = self.settings.mcp_allowlist().get(name)
        if argv is None:
            raise MCPGatewayError(f"MCP server '{name}' is not on the allow-list", 403)
        backend_root = str(PACKAGE_DIR.parent)
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": backend_root, "PYTHONIOENCODING": "utf-8"}
        return StdioServerParameters(command=argv[0], args=argv[1:], env=env, cwd=backend_root)

    @asynccontextmanager
    async def _session(self, name: str) -> AsyncIterator[ClientSession]:
        params = self._params(name)
        with open(os.devnull, "w") as devnull:
            async with stdio_client(params, errlog=devnull) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    with anyio.fail_after(self.settings.mcp_call_timeout_seconds):
                        await session.initialize()
                    yield session

    async def _list_tools(self, name: str) -> tuple[dict[str, Any], list[Any]]:
        async with self._session(name) as s:
            with anyio.fail_after(self.settings.mcp_call_timeout_seconds):
                result = await s.list_tools()
            info = s.server_info
            return ({"name": getattr(info, "name", name), "version": getattr(info, "version", None)}, list(result.tools))

    # ------------------------------------------------------------------------------------------- registry

    def register(self, db: Session, actor: Principal, name: str) -> MCPServerRecord:
        if name not in self.settings.mcp_allowlist():
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.register", name, "denied", {"reason": "not allow-listed"})
            raise MCPGatewayError(f"MCP server '{name}' is not on the allow-list", 403)
        existing = db.scalars(select(MCPServerRecord).where(MCPServerRecord.tenant_id == actor.tenant_id, MCPServerRecord.name == name)).first()
        if existing:
            return existing
        rec = MCPServerRecord(tenant_id=actor.tenant_id, name=name)
        db.add(rec)
        db.flush()
        audit.record(db, actor.tenant_id, actor.user_id, "mcp.register", name, "success", {"server_id": rec.id})
        return rec

    async def discover(self, db: Session, actor: Principal, server: MCPServerRecord) -> list[MCPToolRecord]:
        try:
            info, tools = await self._list_tools(server.name)
        except MCPGatewayError:
            raise
        except Exception as exc:  # noqa: BLE001 - any transport failure marks the server unreachable
            server.status, server.last_error, server.last_checked = "unreachable", f"{type(exc).__name__}: {exc}"[:500], utcnow()
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.discover", server.name, "failed", {"error": server.last_error})
            raise MCPGatewayError(f"Could not reach MCP server '{server.name}': {type(exc).__name__}", 502) from exc
        server.status, server.server_info, server.last_checked, server.last_error = "healthy", info, utcnow(), None
        bundled = server.name in BUNDLED_MCP_SERVERS
        existing = {t.name: t for t in db.scalars(select(MCPToolRecord).where(MCPToolRecord.server_id == server.id))}
        out = []
        for tool in tools:
            raw_desc = tool.description or ""
            schema = tool.input_schema or {}
            flags = scan(raw_desc) + scan(json.dumps(schema))
            ann = tool.annotations
            access = "read" if (ann is not None and ann.read_only_hint is True) else "write"
            shash = _schema_hash(tool.name, schema)
            rec = existing.get(tool.name)
            if rec is None:
                rec = MCPToolRecord(tenant_id=server.tenant_id, server_id=server.id, name=sanitize(tool.name, 100),
                                    description=sanitize(raw_desc), input_schema=schema, schema_hash=shash, access=access)
                if flags:
                    rec.enabled, rec.quarantine_reason = False, "Prompt-injection indicators in description/schema: " + "; ".join(flags)
                elif bundled and access == "read":
                    rec.enabled = True
                else:
                    rec.enabled = False
                    rec.quarantine_reason = "Pending admin review (" + ("write tool" if access == "write" else "non-bundled server") + ")."
                db.add(rec)
            else:
                if rec.schema_hash != shash:
                    rec.enabled = False
                    rec.quarantine_reason = "Schema changed since review; re-review required."
                if flags:
                    rec.enabled = False
                    rec.quarantine_reason = "Prompt-injection indicators in description/schema: " + "; ".join(flags)
                rec.description, rec.input_schema, rec.access = sanitize(raw_desc), schema, access
            out.append(rec)
        db.flush()
        audit.record(db, actor.tenant_id, actor.user_id, "mcp.discover", server.name, "success",
                     {"tools": [t.name for t in out], "quarantined": [t.name for t in out if t.quarantine_reason and not t.enabled]})
        return out

    def enable_tool(self, db: Session, actor: Principal, tool: MCPToolRecord) -> MCPToolRecord:
        """Admin review: enable a tool and pin its current schema. Injection-flagged tools cannot be enabled."""
        if tool.quarantine_reason and tool.quarantine_reason.startswith("Prompt-injection"):
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.tool.enable", tool.name, "denied", {"reason": tool.quarantine_reason})
            raise MCPGatewayError("Tool is quarantined for prompt-injection indicators and cannot be enabled", 409)
        tool.enabled, tool.quarantine_reason = True, None
        tool.schema_hash = _schema_hash(tool.name, tool.input_schema)
        audit.record(db, actor.tenant_id, actor.user_id, "mcp.tool.enable", tool.name, "success", {"schema_hash": tool.schema_hash})
        return tool

    async def health(self, db: Session, server: MCPServerRecord) -> dict[str, Any]:
        try:
            async with self._session(server.name) as s:
                with anyio.fail_after(self.settings.mcp_call_timeout_seconds):
                    await s.send_ping()
            server.status, server.last_error = "healthy", None
        except Exception as exc:  # noqa: BLE001
            server.status, server.last_error = "unreachable", f"{type(exc).__name__}"
        server.last_checked = utcnow()
        return {"server": server.name, "status": server.status, "checked_at": server.last_checked.isoformat()}

    # ------------------------------------------------------------------------------------------- invocation

    async def invoke(self, db: Session, actor: Principal, server: MCPServerRecord, tool: MCPToolRecord, arguments: dict[str, Any]) -> dict[str, Any]:
        def deny(reason: str, status: int = 403) -> MCPGatewayError:
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.invoke", f"{server.name}/{tool.name}", "denied", {"reason": reason})
            return MCPGatewayError(reason, status)

        if not actor.can("mcp:invoke_read"):
            raise deny("Missing permission mcp:invoke_read")
        if not tool.enabled:
            raise deny(f"Tool is not enabled: {tool.quarantine_reason or 'disabled'}", 409)
        if tool.access != "read":
            raise deny("Write tools cannot be invoked directly; they require an approved remediation plan", 403)
        try:
            jsonschema.validate(arguments, tool.input_schema)
        except jsonschema.ValidationError as exc:
            raise deny(f"Arguments do not match the tool schema: {exc.message}", 422) from exc

        try:
            async with self._session(server.name) as s:
                with anyio.fail_after(self.settings.mcp_call_timeout_seconds):
                    live = {t.name: t for t in (await s.list_tools()).tools}
                lt = live.get(tool.name)
                drifted = lt is None or _schema_hash(lt.name, lt.input_schema or {}) != tool.schema_hash
                result = None
                if not drifted:
                    with anyio.fail_after(self.settings.mcp_call_timeout_seconds):
                        result = await s.call_tool(tool.name, arguments)
        except MCPGatewayError:
            raise
        except TimeoutError as exc:
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.invoke", f"{server.name}/{tool.name}", "failed", {"error": "timeout"})
            raise MCPGatewayError("MCP call timed out", 504) from exc
        except Exception as exc:  # noqa: BLE001
            audit.record(db, actor.tenant_id, actor.user_id, "mcp.invoke", f"{server.name}/{tool.name}", "failed", {"error": type(exc).__name__})
            raise MCPGatewayError(f"MCP call failed: {type(exc).__name__}", 502) from exc

        if drifted:  # raised outside the transport context so it is not wrapped by the task group
            tool.enabled, tool.quarantine_reason = False, "Schema changed since review; re-review required."
            db.flush()
            raise deny("Live tool schema differs from the reviewed schema; tool disabled", 409)
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        raw = "\n".join(texts)
        structured = result.structured_content
        if structured is None:
            try:
                parsed = json.loads(raw)
                structured = parsed if isinstance(parsed, dict) else None
            except ValueError:
                structured = None
        flags = scan(raw) + scan(json.dumps(structured or {}))
        output = {
            "is_error": bool(result.is_error),
            "text": redact(sanitize(raw, MAX_OUTPUT_CHARS)),
            "structured": redact(structured) if structured else None,
            "untrusted_content_flags": flags,
            "trust_note": "Tool output is untrusted data. It is displayed, never executed or used as instructions.",
        }
        audit.record(db, actor.tenant_id, actor.user_id, "mcp.invoke", f"{server.name}/{tool.name}",
                     "failed" if result.is_error else "success", {"arguments": arguments, "flags": flags})
        return output
