"""Trust and integration API: policy, audit, approvals, governance, Legacy X-Ray, Bridge Studio."""

from __future__ import annotations

import hashlib
from typing import Any

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import ApiError, envelope, require
from app.core import audit, db, policy
from app.core.config import get_settings
from app.core.security import Actor, current_actor, load_actor
from app.integrations.legacy import parsers, xray
from app.integrations.mcp import bridge
from app.integrations.mcp.registry import UntrustedToolError, ToolSpec, invocation_count
from app.services import approvals, catalog, security_lab
from app.services.tools import registry

router = APIRouter()


# ---------------------------------------------------------------- policy

class EvaluateBody(BaseModel):
    action: str = Field(max_length=40)
    resource: str = Field(default="lab", max_length=200)
    label: str = Field(default="INTERNAL", pattern=r"^(PUBLIC|INTERNAL|RESTRICTED|UNKNOWN)$")
    destination: str = Field(default="none", max_length=40)
    tool: str | None = Field(default=None, max_length=80)
    as_user: str | None = Field(default=None, max_length=64)
    instruction_source: str = Field(default="user", pattern=r"^(user|retrieved_content|agent)$")


@router.post("/api/policy/evaluate")
def evaluate(request: Request, body: EvaluateBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Evaluate a hypothetical request. Never executes anything; the decision is recorded."""
    subject = actor
    if body.as_user and body.as_user != actor.id:
        if actor.role not in ("security_officer", "auditor"):
            raise ApiError(403, "not_permitted", "Only security officers and auditors may evaluate on behalf of another user.")
        subject = load_actor(body.as_user) or actor
    reg = registry()
    d = policy.evaluate(subject, policy.PolicyRequest(
        action=body.action, resource=f"lab:{body.resource}", label=body.label, destination=body.destination, tool=body.tool,
        instruction_source=body.instruction_source,
        tool_registered=(body.tool in reg.tools) if body.tool else None, tool_pinned=(body.tool in reg.tools) if body.tool else None))
    return envelope(request, {**d.as_dict(), "evaluated_for": subject.id, "executed": False})


@router.get("/api/policy/decisions")
def decisions(request: Request, decision: str | None = Query(None, pattern=r"^(ALLOW|DENY)$"), limit: int = Query(200, ge=1, le=1000),
              actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    rows_ = policy.list_decisions(decision, limit)
    if actor.role not in ("security_officer", "auditor"):
        rows_ = [r for r in rows_ if r["actor"] == actor.id]
    return envelope(request, rows_)


@router.get("/api/policy/catalog")
def policy_catalog(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    counts = {r["policy_id"]: r["n"] for r in db.query("SELECT policy_id, COUNT(*) n FROM policy_decisions WHERE decision='DENY' GROUP BY policy_id")}
    cat = [{**p, "denials": counts.get(p["id"], 0)} for p in policy.load_policy_catalog()]
    return envelope(request, {"version": policy.POLICY_SET_VERSION, "policies": cat, "role_actions": {k: sorted(v) for k, v in policy.ROLE_ACTIONS.items()},
                              "approver_roles": {k: sorted(v) for k, v in policy.APPROVER_ROLES.items()}})


@router.post("/api/policy/tests/run")
def run_security_tests(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    if actor.role not in ("security_officer", "auditor", "fde", "enterprise_architect"):
        raise ApiError(403, "not_permitted", "Security Test Lab is available to security, audit and engineering personas.")
    results = security_lab.run()
    audit.append(actor.id, "security_lab.run", f"{sum(r['passed'] for r in results)}/{len(results)} scenarios passed", {"results": [{k: r[k] for k in ('id', 'observed', 'passed')} for r in results]})
    return envelope(request, results)


@router.get("/api/compliance/matrix")
def compliance(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, catalog.COMPLIANCE, warnings=["Informational mapping only. Requires qualified compliance review. No certification is claimed."])


# ---------------------------------------------------------------- audit

@router.get("/api/audit/events")
def audit_events(request: Request, limit: int = Query(200, ge=1, le=2000), offset: int = Query(0, ge=0), kind: str | None = Query(None, max_length=60),
                 actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    if actor.role not in ("security_officer", "auditor"):
        events = [e for e in audit.list_events(limit, kind, offset) if e["actor"] == actor.id]
    else:
        events = audit.list_events(limit, kind, offset)
    total = db.query_one("SELECT COUNT(*) n FROM audit_events")["n"]
    return envelope(request, {"total": total, "items": events})


class VerifyBody(BaseModel):
    events: list[dict[str, Any]] | None = None


@router.post("/api/audit/verify")
def audit_verify(request: Request, body: VerifyBody | None = None, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "audit_verify", "audit:chain", "INTERNAL")
    return envelope(request, audit.verify(body.events if body and body.events else None))


@router.get("/api/audit/export")
def audit_export(actor: Actor = Depends(current_actor)) -> Response:
    require(actor, "audit_export", "audit:chain", "RESTRICTED")
    import json

    chain = audit.export_chain()
    body = json.dumps({"verification": audit.verify(chain), "events": chain}, indent=1)
    audit.append(actor.id, "audit.exported", f"Audit chain exported ({len(chain)} events)", {"sha256": hashlib.sha256(body.encode()).hexdigest()})
    return Response(body, media_type="application/json", headers={"Content-Disposition": "attachment; filename=flying_florina_audit_chain.json"})


# ---------------------------------------------------------------- approvals + governance

@router.get("/api/approvals")
def list_approvals(request: Request, status: str | None = Query(None, max_length=20), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    items = approvals.list_all(status)
    for a in items:
        can = policy.APPROVER_ROLES.get(a["kind"], set())
        a["you_can_approve"] = a["status"] == "pending" and actor.role in can and a["requested_by"] != actor.id and not a["expired"]
        a["you_can_execute"] = a["status"] == "approved" and not a["executed"] and actor.role in policy.ROLE_ACTIONS and "write" in policy.ROLE_ACTIONS[actor.role]
        if actor.role == "guest":
            a["payload"] = {"withheld": "Guest persona cannot view approval payloads."}
            a["idempotency_key"] = None
    return envelope(request, items)


class DecideBody(BaseModel):
    note: str = Field(default="", max_length=500)


@router.post("/api/approvals/{approval_id}/approve")
def approve(request: Request, approval_id: str, body: DecideBody | None = None, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return _decide(request, approval_id, actor, True, body.note if body else "")


@router.post("/api/approvals/{approval_id}/reject")
def reject(request: Request, approval_id: str, body: DecideBody | None = None, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return _decide(request, approval_id, actor, False, body.note if body else "")


def _decide(request: Request, approval_id: str, actor: Actor, ok: bool, note: str) -> dict[str, Any]:
    try:
        return envelope(request, approvals.decide(approval_id, actor, ok, note))
    except approvals.ApprovalError as e:
        raise ApiError(404 if e.code == "not_found" else 409 if e.code in ("already_decided", "expired") else 403, e.code, e.message, e.decision) from e


class ExecuteBody(BaseModel):
    idempotency_key: str = Field(max_length=64)


@router.post("/api/approvals/{approval_id}/execute")
def execute(request: Request, approval_id: str, body: ExecuteBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    try:
        return envelope(request, approvals.execute(approval_id, actor, body.idempotency_key),
                        warnings=["Simulated write into the synthetic demo database. No external system was changed."])
    except approvals.ApprovalError as e:
        raise ApiError(404 if e.code == "not_found" else 403, e.code, e.message, e.decision) from e


class KillBody(BaseModel):
    on: bool


@router.post("/api/governance/kill-switch")
def kill_switch(request: Request, body: KillBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "admin_kill_switch", "governance:kill_switch", "INTERNAL")
    policy.set_kill_switch(body.on, actor)
    return envelope(request, {"kill_switch": "on" if body.on else "off"})


@router.get("/api/governance/state")
def governance_state(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, {"kill_switch": policy.kill_switch_active(),
                              "decisions": db.query_one("SELECT COUNT(*) n, SUM(CASE WHEN decision='DENY' THEN 1 ELSE 0 END) denied FROM policy_decisions"),
                              "tool_invocations": db.query("SELECT tool, status, COUNT(*) n FROM tool_invocations GROUP BY tool, status ORDER BY tool"),
                              "export_tool_executions": invocation_count("records.export_email"),
                              "pending_approvals": db.query_one("SELECT COUNT(*) n FROM approvals WHERE status='pending'")["n"]})


@router.get("/api/governance/classification")
def classification(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    docs = db.query("SELECT classification, COUNT(*) n FROM documents GROUP BY classification")
    wos = db.query("SELECT classification, COUNT(*) n FROM work_orders GROUP BY classification")
    matrix = []
    for p in catalog.PERSONAS:
        a = load_actor(p["user_id"])
        if a:
            matrix.append({"user": a.id, "persona": p["persona"], **{lbl: policy.label_allows(a, lbl)[0] for lbl in policy.LABELS}})
    return envelope(request, {"documents": docs, "work_orders": wos, "access_matrix": matrix,
                              "labels": {"PUBLIC": "Anyone authenticated", "INTERNAL": "Home organization, non-guest", "RESTRICTED": "Restricted group + synthetic attribute",
                                         "UNKNOWN": "Denied until classified (security officer review only)"}})


# ---------------------------------------------------------------- Legacy X-Ray

@router.post("/api/legacy/import")
async def legacy_import(request: Request, file: UploadFile = File(...), actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "import", "legacy:import", "INTERNAL")
    limit = get_settings().max_upload_bytes
    raw = await file.read(limit + 1)
    try:
        result = parsers.parse_upload(file.filename or "upload", raw, limit)
    except parsers.ImportRejected as e:
        audit.append(actor.id, "legacy.import_rejected", f"{e.code}: {file.filename}", {"code": e.code})
        raise ApiError(422, e.code, e.message) from e
    sha = hashlib.sha256(raw).hexdigest()
    iid = xray.store_import(actor.id, result["filename"], len(raw), sha, result)
    audit.append(actor.id, "legacy.imported", f"{result['kind']} {result['filename']}", {"import_id": iid, "sha256": sha})
    return envelope(request, {"import_id": iid, "sha256": sha, **result}, warnings=["Parsed as metadata only; nothing was executed."])


class FixtureBody(BaseModel):
    name: str = Field(max_length=120)


@router.get("/api/legacy/fixtures")
def legacy_fixtures(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, xray.bundled_fixture_paths())


@router.post("/api/legacy/import-fixture")
def legacy_import_fixture(request: Request, body: FixtureBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "import", "legacy:import", "INTERNAL")
    if body.name not in xray.bundled_fixture_paths():
        raise ApiError(404, "unknown_fixture", "Not a bundled fixture.")
    res = xray.parse_bundled([body.name])[0]
    return envelope(request, res)


@router.get("/api/legacy/systems")
def legacy_systems(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "legacy:systems", "INTERNAL")
    from app.services import data

    return envelope(request, {"applications": data.applications(), "dependencies": data.app_dependencies(),
                              "imports": db.query("SELECT id, ts, actor, filename, kind, size, sha256 FROM legacy_imports ORDER BY ts DESC")})


@router.get("/api/legacy/graph")
def legacy_graph(request: Request, include_uploads: bool = True, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "legacy:graph", "INTERNAL")
    ls = xray.landscape(include_uploads=include_uploads)
    ls.pop("parsed", None)
    return envelope(request, ls)


@router.post("/api/legacy/recommend")
def legacy_recommend(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "legacy:recommend", "INTERNAL")
    ls = xray.landscape()
    current = {"systems": [n for n in ls["nodes"] if n["type"] == "system"], "edges": [e for e in ls["edges"] if e["kind"] != "contains" and not e["source"].startswith(("T:", "V:"))]}
    target = {"layers": ["Agents (Flying_Florina workflows)", "MCP tools (pinned, read-only first)", "Policy gateway (deny-by-default)",
                         "API gateway + typed facades / ACL", "Batch bridge + (conditional) CDC events", "Legacy core unchanged: MRO_CORE, Java ERP, COBOL batch"],
              "new_components": ["Part availability adapter (R1)", "MCP facade (R8)", "Validated batch bridge (R4)", "ERP facade + ACL (R2, R3)"]}
    diff = [{"change": "add", "component": c} for c in target["new_components"]] + [
        {"change": "restrict", "component": "Java ERP /admin/sql endpoint (firewall, then retire)"},
        {"change": "keep", "component": "MRO_CORE schema and transactions (no rewrite)"},
        {"change": "decide later", "component": "CDC on MRO_STOCK_LOC (R5), documented ERP projections (R7)"}]
    return envelope(request, {"recommendations": xray.recommendations(ls), "roadmap": xray.roadmap(), "current_state": current, "target_state": target,
                              "diff": diff, "unknowns": ls["unknowns"], "summary": ls["summary"], "matrix": catalog.INTEGRATION_MATRIX,
                              "executive_brief": ("Keep the core, wrap it: start with a read-only parts adapter and MCP tool, validate the nightly batch, "
                                                  "then put a facade with an anti-corruption layer in front of the Java ERP service. Answer the five unknowns before CDC "
                                                  "or any ERP/IFS integration. Effort figures are assumptions.")})


# ---------------------------------------------------------------- Bridge Studio

class GenerateBody(BaseModel):
    capability: str = Field(default="part_availability", max_length=60)
    source_id: str = Field(default="mro_view", max_length=60)
    scopes: list[str] = Field(default_factory=lambda: ["inventory.read"], max_length=5)


@router.get("/api/bridge/sources")
def bridge_sources(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    return envelope(request, {"sources": bridge.DISCOVERED_SOURCES, "capabilities": bridge.CAPABILITIES})


@router.post("/api/bridge/generate")
def bridge_generate(request: Request, body: GenerateBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "generate_code", f"bridge:{body.capability}", "INTERNAL")
    if any(s not in ("inventory.read",) for s in body.scopes):
        raise ApiError(422, "scope_not_allowed", "Only the read-only scope inventory.read is allowed for generated adapters.")
    try:
        res = bridge.generate(actor.id, body.capability, body.source_id, body.scopes)
    except ValueError as err:
        raise ApiError(422, "unsupported_capability", str(err)) from err
    audit.append(actor.id, "bridge.generated", f"{res['bundle_id']} {body.capability}", {"bundle_id": res["bundle_id"], "files": len(res["files"])})
    return envelope(request, res, warnings=["Generated code is preview-only until you run its tests in the sandbox."])


class TestBody(BaseModel):
    bundle_id: str = Field(pattern=r"^BRG-[0-9a-f]{12}$")


@router.post("/api/bridge/test")
def bridge_test(request: Request, body: TestBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "run_sandbox_tests", f"bridge:{body.bundle_id}", "INTERNAL")
    try:
        res = bridge.run_tests(body.bundle_id)
    except FileNotFoundError as err:
        raise ApiError(404, "not_found", "Bundle not found.") from err
    audit.append(actor.id, "bridge.tested", f"{body.bundle_id}: {res['passed']} passed, {res['failed']} failed", {"bundle_id": body.bundle_id, "exit_code": res["exit_code"]})
    return envelope(request, res)


@router.get("/api/bridge/tools")
def bridge_tools(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    reg = registry()
    pins = reg.allowlist()
    tools = []
    for name, spec in reg.tools.items():
        tools.append({**spec.describe(), "pinned_version": pins.get(name, {}).get("version"), "pin_ok": pins.get(name, {}).get("schema_sha256") == spec.schema_sha256,
                      "invocations": invocation_count(name)})
    return envelope(request, {"tools": tools, "rejected": reg.rejected, "allowlist": list(pins.values())})


@router.get("/api/bridge/mcp-discover")
def bridge_mcp_discover(request: Request, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    require(actor, "read", "mcp:demo_maintenance", "INTERNAL")
    from app.integrations.mcp.client import discover_demo_server

    return envelope(request, discover_demo_server(actor))


class RegisterBody(BaseModel):
    name: str = Field(max_length=80)
    version: str = Field(max_length=20)


@router.post("/api/bridge/register-tool")
def bridge_register(request: Request, body: RegisterBody, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    """Attempt to register a tool definition. Only allowlisted, pinned tools succeed (POL-006)."""
    require(actor, "generate_code", f"tool:{body.name}", "INTERNAL")

    class _Args(BaseModel):
        value: str

    spec = ToolSpec(body.name, body.version, "user-submitted tool", "read", "INTERNAL", _Args, lambda value: value)
    try:
        registry().register(spec)
        registered = True
        reason = "registered"
    except UntrustedToolError as e:
        registered, reason = False, str(e)
    audit.append(actor.id, "tool.register_attempt", f"{body.name}@{body.version}: {reason}", {"registered": registered})
    return envelope(request, {"registered": registered, "reason": reason, "policy_id": "POL-006"})


@router.get("/api/bridge/{bundle_id}")
def bridge_bundle(request: Request, bundle_id: str, actor: Actor = Depends(current_actor)) -> dict[str, Any]:
    r = db.query_one("SELECT * FROM bridge_bundles WHERE id = ?", (bundle_id,))
    if not r:
        raise ApiError(404, "not_found", "Bundle not found.")
    root = bridge.bundle_path(bundle_id)
    preview = {}
    if root:
        for rel in ("adapter/app.py", "adapter/models.py", "mcp_server/server.py", "tests/test_contract.py", "README.md", "THREAT_MODEL.md", "openapi.json"):
            p = root / rel
            if p.exists():
                preview[rel] = p.read_text()[:20000]
    return envelope(request, {"bundle_id": bundle_id, "ts": r["ts"], "capability": r["capability"], "files": db.jload(r["files_json"], []),
                              "test_result": db.jload(r["test_result_json"]), "preview": preview, "static_checks": bridge.static_checks(root) if root else []})


@router.get("/api/bridge/{bundle_id}/download")
def bridge_download(bundle_id: str, actor: Actor = Depends(current_actor)) -> Response:
    require(actor, "export", f"bridge:{bundle_id}", "INTERNAL", destination="local_download")
    try:
        blob = bridge.zip_bundle(bundle_id)
    except FileNotFoundError as err:
        raise ApiError(404, "not_found", "Bundle not found.") from err
    return Response(blob, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={bundle_id}.zip"})
