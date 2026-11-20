"""Shield extensions to the MCP gateway: whole-server manifest pinning and emergency revocation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.context import AppContext
from florome.mcp.gateway import manifest_hash
from florome.models import MCPServerRecord, MCPToolRecord
from florome.security import audit
from florome.security.rbac import Principal
from florome.shield.control import authorize
from florome.shield.models import MCPServerManifest


async def pin(db: Session, ctx: AppContext, p: Principal, server: MCPServerRecord) -> MCPServerManifest:
    authorize(db, ctx.settings, p, "mcp.pin", {"id": server.id})
    info, tools = await ctx.mcp._list_tools(server.name)  # noqa: SLF001 - same transport as discovery
    h = manifest_hash(info, tools)
    man = db.scalars(select(MCPServerManifest).where(MCPServerManifest.server_id == server.id)).first()
    if man is None:
        man = MCPServerManifest(tenant_id=server.tenant_id, server_id=server.id, manifest_hash=h, server_identity=info, pinned_by=p.user_id)
        db.add(man)
    else:
        man.manifest_hash, man.server_identity, man.pinned_by, man.revoked, man.revoked_reason = h, info, p.user_id, False, None
    audit.record(db, p.tenant_id, p.user_id, "shield.mcp.pin", server.name, "success", {"manifest_hash": h, "tools": len(tools)})
    db.flush()
    return man


def revoke(db: Session, ctx: AppContext, p: Principal, server: MCPServerRecord, reason: str) -> MCPServerManifest:
    authorize(db, ctx.settings, p, "mcp.revoke", {"id": server.id})
    man = db.scalars(select(MCPServerManifest).where(MCPServerManifest.server_id == server.id)).first()
    if man is None:
        man = MCPServerManifest(tenant_id=server.tenant_id, server_id=server.id, manifest_hash="", pinned_by=p.user_id)
        db.add(man)
    man.revoked, man.revoked_reason = True, reason[:500] or "emergency revocation"
    for t in db.scalars(select(MCPToolRecord).where(MCPToolRecord.server_id == server.id)):
        t.enabled, t.quarantine_reason = False, f"Server revoked: {man.revoked_reason}"
    audit.record(db, p.tenant_id, p.user_id, "shield.mcp.revoke", server.name, "success", {"reason": man.revoked_reason})
    db.flush()
    return man
