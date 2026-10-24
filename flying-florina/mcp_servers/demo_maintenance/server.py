"""Demo maintenance MCP server (stdio, official Python MCP SDK).

Local and synthetic only. Exposes three read-only tools over the Flying_Florina
read models. Identity: launched with FF_MCP_TOKEN, a signed token whose
audience must be 'ff-mcp-demo'. Every call re-verifies the token and runs the
deterministic policy engine before touching data. MCP is the agent interface;
the policy engine is the control.

Run from the repository root:
    backend/.venv/bin/python -m mcp_servers.demo_maintenance.server
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from app.core import policy  # noqa: E402
from app.core.security import TokenError, load_actor, verify_token  # noqa: E402
from app.retrieval.search import search  # noqa: E402
from app.services import data  # noqa: E402

AUDIENCE = "ff-mcp-demo"
server = MCPServer(name="ff-demo-maintenance", version="1.0.0",
                   instructions="Synthetic, read-only maintenance tools. Every call is authorized by the Flying_Florina policy engine.")


def _authorize(action: str, resource: str, label: str):
    try:
        claims = verify_token(os.environ.get("FF_MCP_TOKEN"), audience=AUDIENCE)
    except TokenError as err:
        return None, {"error": err.code, "message": err.message}
    actor = load_actor(claims["sub"])
    if actor is None:
        return None, {"error": "unknown_user"}
    d = policy.evaluate(actor, policy.PolicyRequest(action=action, resource=f"mcp:{resource}", label=label))
    if not d.allowed:
        return None, {"error": "policy_denied", "policy_id": d.policy_id, "reason": d.reason}
    return actor, None


@server.tool(name="get_fleet_overview", description="Synthetic fleet status counts and anomaly list.")
def get_fleet_overview() -> dict:
    actor, err = _authorize("read", "fleet", "INTERNAL")
    if err:
        return err
    f = data.fleet_overview()
    return {k: f[k] for k in ("total_aircraft", "by_status", "available_pct", "aog_count", "open_work_orders", "anomaly_aircraft", "as_of")}


@server.tool(name="get_part_availability", description="Verified availability for one synthetic part number.")
def get_part_availability(part_number: str) -> dict:
    actor, err = _authorize("read", f"part:{part_number}", "INTERNAL")
    if err:
        return err
    if not part_number.startswith("P-") or len(part_number) > 12:
        return {"error": "invalid_part_number"}
    return {"part_number": part_number, "availability": data.part_availability(part_number)}


@server.tool(name="search_documents", description="Access-filtered search over synthetic technical references.")
def search_documents(query: str) -> dict:
    actor, err = _authorize("search", "documents", "PUBLIC")
    if err:
        return err
    res = search(actor, query[:300], 5)
    return {"results": [{k: r[k] for k in ("doc_id", "revision", "title", "status", "flags")} for r in res["results"]],
            "withheld_by_policy": res["withheld_by_policy"]}


if __name__ == "__main__":
    server.run("stdio")
