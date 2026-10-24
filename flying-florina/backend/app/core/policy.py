"""Deterministic policy engine (deny by default).

Every consequential operation in Flying_Florina is evaluated here *before* any
tool executes. No language model participates in a decision: the rules are
plain Python, versioned, unit-tested, and each decision is persisted with the
full list of checks that were evaluated.

Policy metadata (titles, versions, descriptions, references) lives in
fixtures/policies/policies.yaml; the executable logic lives below and is keyed
by the same policy IDs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml

from app.core import audit, db
from app.core.config import FIXTURES_DIR, get_settings
from app.core.security import Actor
from app.core.util import new_id, now_iso

POLICY_SET_VERSION = "2026.10.1"

LABELS = ["PUBLIC", "INTERNAL", "RESTRICTED", "UNKNOWN"]
HOME_ORG = "FF-Demo-MRO"

ROLE_ACTIONS: dict[str, set[str]] = {
    "guest": {"read", "search", "query"},
    "executive": {"read", "search", "query", "export", "simulate"},
    "maintenance_planner": {"read", "search", "query", "draft_write", "write", "approve", "export", "simulate", "tool_call"},
    "technician": {"read", "search", "query", "draft_write", "tool_call", "simulate"},
    "reliability_engineer": {"read", "search", "query", "draft_write", "write", "approve", "export", "simulate", "tool_call"},
    "enterprise_architect": {"read", "search", "query", "import", "generate_code", "run_sandbox_tests", "tool_call", "export", "simulate"},
    "security_officer": {"read", "search", "query", "admin_kill_switch", "approve", "audit_verify", "audit_export",
                         "run_sandbox_tests", "export", "tool_call", "role_change"},
    "auditor": {"read", "search", "query", "audit_verify", "audit_export", "export"},
    "fde": {"read", "search", "query", "import", "generate_code", "run_sandbox_tests", "tool_call", "export", "simulate"},
    # Agents act on behalf of a human; their effective rights are the
    # intersection of this set and the requesting human's set.
    "agent": {"read", "search", "query", "tool_call", "draft_write", "simulate"},
}

RESTRICTED_ROLES = {"maintenance_planner", "technician", "reliability_engineer", "security_officer", "auditor"}

APPROVER_ROLES: dict[str, set[str]] = {
    "work_order": {"maintenance_planner", "reliability_engineer"},
    "bridge_test": {"security_officer", "enterprise_architect"},
    "quality_disposition": {"reliability_engineer", "security_officer"},
}

INTERNAL_DESTINATIONS = {"local_download", "internal_share", "none"}


@dataclass
class PolicyRequest:
    action: str
    resource: str = ""
    label: str = "INTERNAL"
    destination: str = "none"
    tool: str | None = None
    purpose: str = ""
    approval_id: str | None = None
    approval_kind: str | None = None
    idempotency_key: str | None = None
    instruction_source: str = "user"  # user | retrieved_content | agent
    model_target: str | None = None
    target_actor: str | None = None
    tool_registered: bool | None = None
    tool_pinned: bool | None = None
    run_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Check:
    policy_id: str
    name: str
    result: str  # pass | fail | n/a
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {"policy_id": self.policy_id, "name": self.name, "result": self.result, "detail": self.detail}


@dataclass
class Decision:
    id: str
    decision: str  # ALLOW | DENY
    policy_id: str
    reason: str
    checks: list[Check]
    ts: str
    actor: str
    role: str
    request: PolicyRequest
    eval_ms: float

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "decision": self.decision,
            "policy_id": self.policy_id,
            "reason": self.reason,
            "checks": [c.as_dict() for c in self.checks],
            "ts": self.ts,
            "actor": self.actor,
            "role": self.role,
            "action": self.request.action,
            "resource": self.request.resource,
            "label": self.request.label,
            "destination": self.request.destination,
            "tool": self.request.tool,
            "policy_set_version": POLICY_SET_VERSION,
            "eval_ms": round(self.eval_ms, 3),
        }


def load_policy_catalog() -> list[dict[str, Any]]:
    with open(FIXTURES_DIR / "policies" / "policies.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["policies"]


def kill_switch_active() -> bool:
    r = db.query_one("SELECT value FROM governance_state WHERE key = 'kill_switch'")
    return bool(r and r["value"] == "on")


def set_kill_switch(on: bool, actor: Actor) -> None:
    with db.session(write=True) as conn:
        conn.execute(
            "INSERT INTO governance_state(key, value) VALUES ('kill_switch', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            ("on" if on else "off",),
        )
        if on:
            conn.execute("UPDATE workflow_runs SET status = 'cancelled' WHERE status IN ('running', 'queued')")
        audit.append(actor.id, "governance.kill_switch", f"Kill switch turned {'ON' if on else 'OFF'}", {"on": on}, conn)


def label_allows(actor: Actor, label: str) -> tuple[bool, str]:
    if label == "PUBLIC":
        return True, "PUBLIC data is readable by every authenticated actor."
    if label == "INTERNAL":
        if actor.org != HOME_ORG:
            return False, f"INTERNAL data is limited to organization {HOME_ORG}; actor belongs to {actor.org}."
        if actor.role == "guest":
            return False, "Guest persona is limited to PUBLIC data."
        return True, "Actor is an internal member of the owning organization."
    if label == "RESTRICTED":
        if actor.org != HOME_ORG:
            return False, "RESTRICTED data never leaves the owning organization."
        if actor.role not in RESTRICTED_ROLES and not actor.is_agent:
            return False, f"Role '{actor.role}' is not in the RESTRICTED access group."
        if "restricted-sim" not in actor.clearances and not actor.is_agent:
            return False, "Actor lacks the synthetic 'restricted-sim' authorization attribute."
        return True, "Role and synthetic authorization attribute satisfy RESTRICTED access."
    # UNKNOWN or anything unexpected: deny until a human classifies it.
    if actor.role == "security_officer":
        return True, "UNKNOWN classification may be opened only by a security officer for review."
    return False, "Classification is UNKNOWN; sensitive operations are denied until a human classifies the resource."


def _approval_state(approval_id: str) -> dict[str, Any] | None:
    return db.query_one("SELECT * FROM approvals WHERE id = ?", (approval_id,))


def evaluate(actor: Actor, req: PolicyRequest, record: bool = True, on_behalf_of: Actor | None = None) -> Decision:
    """Evaluate a request. Order matters: the first failing check decides."""
    started = time.perf_counter()
    settings = get_settings()
    checks: list[Check] = []

    def deny(pid: str, name: str, reason: str) -> Decision:
        checks.append(Check(pid, name, "fail", reason))
        return _finish("DENY", pid, reason)

    def ok(pid: str, name: str, detail: str) -> None:
        checks.append(Check(pid, name, "pass", detail))

    def _finish(decision: str, pid: str, reason: str) -> Decision:
        d = Decision(
            id=new_id("DEC"), decision=decision, policy_id=pid, reason=reason, checks=checks, ts=now_iso(),
            actor=actor.id, role=actor.role, request=req, eval_ms=(time.perf_counter() - started) * 1000,
        )
        if record:
            _record(d, on_behalf_of)
        return d

    # POL-012 identity
    if not actor or not actor.id:
        return deny("POL-012", "Identity required", "No authenticated identity was presented.")
    ok("POL-012", "Identity required", f"Authenticated as {actor.id} ({actor.role}).")

    # POL-009 kill switch
    if req.action not in {"admin_kill_switch", "audit_verify", "audit_export", "read"} and kill_switch_active():
        return deny("POL-009", "Governance kill switch", "Kill switch is ON: new tool calls and workflows are stopped.")
    ok("POL-009", "Governance kill switch", "Kill switch is off (or action is exempt).")

    # POL-011 prompt injection / untrusted instruction source
    if req.instruction_source == "retrieved_content" and req.action in {"tool_call", "export", "write", "draft_write"}:
        return deny("POL-011", "Untrusted instruction source",
                    "The action was requested by text inside retrieved content, not by the authenticated user.")
    ok("POL-011", "Untrusted instruction source", f"Instruction source: {req.instruction_source}.")

    # POL-007 privilege escalation
    if req.action in {"role_change", "policy_change"}:
        if actor.is_agent:
            return deny("POL-007", "No self-privilege escalation", "Agents can never change roles or policies.")
        if req.target_actor == actor.id:
            return deny("POL-007", "No self-privilege escalation", "An actor cannot change its own role or entitlements.")
        if req.action == "policy_change":
            return deny("POL-007", "No self-privilege escalation", "Policies are code; changes go through version control review, not the API.")
    ok("POL-007", "No self-privilege escalation", "Request does not alter the actor's own privileges.")

    # POL-006 tool allowlist and version pinning
    if req.tool is not None or req.action == "tool_call":
        if not req.tool or req.tool_registered is False:
            return deny("POL-006", "Tool allowlist & pinning", f"Tool '{req.tool}' is not on the pinned allowlist.")
        if req.tool_pinned is False:
            return deny("POL-006", "Tool allowlist & pinning", f"Tool '{req.tool}' version or schema hash differs from the pinned value.")
        ok("POL-006", "Tool allowlist & pinning", f"Tool '{req.tool}' is allowlisted with a matching pinned schema.")

    # POL-008 model calls
    if req.action == "model_call":
        target = req.model_target or ""
        local = target.startswith("http://127.0.0.1") or target.startswith("http://localhost")
        if not local:
            return deny("POL-008", "Local models only", f"Model endpoint '{target}' is not a loopback address.")
        if not settings.llm_enabled:
            return deny("POL-008", "Local models only", "Optional local LLM is disabled (LLM_ENABLED=false).")
        ok("POL-008", "Local models only", "Loopback model endpoint and LLM enabled.")

    # POL-004 exfiltration
    if req.action == "export":
        if req.destination not in INTERNAL_DESTINATIONS:
            if req.label in {"RESTRICTED", "UNKNOWN"}:
                return deny("POL-004", "No external exfiltration",
                            f"{req.label} records may never be sent to destination '{req.destination}'.")
            if settings.offline_mode:
                return deny("POL-004", "No external exfiltration",
                            f"OFFLINE_MODE forbids sending data to external destination '{req.destination}'.")
            return deny("POL-004", "No external exfiltration",
                        "External destinations are not configured as approved connectors in this demo.")
        ok("POL-004", "No external exfiltration", f"Destination '{req.destination}' is local.")

    # POL-001 deny by default / POL-002 RBAC
    if actor.role not in ROLE_ACTIONS:
        return deny("POL-001", "Deny by default", f"Role '{actor.role}' has no grants; everything is denied.")
    allowed_actions = ROLE_ACTIONS[actor.role]
    if on_behalf_of is not None:
        allowed_actions = allowed_actions & ROLE_ACTIONS.get(on_behalf_of.role, set())
    if req.action not in allowed_actions:
        who = f"role '{actor.role}'" + (f" acting for '{on_behalf_of.role}'" if on_behalf_of else "")
        return deny("POL-002", "Role-based access", f"Action '{req.action}' is not granted to {who}.")
    ok("POL-002", "Role-based access", f"Action '{req.action}' is granted to role '{actor.role}'.")

    # POL-003 classification / ABAC
    effective = on_behalf_of or actor
    if req.extra.get("require_home_org") and effective.org != HOME_ORG:
        return deny("POL-003", "Classification & attributes",
                    f"Operational workflows are limited to organization {HOME_ORG}; actor belongs to {effective.org}.")
    allowed, why = label_allows(effective, req.label)
    if not allowed:
        return deny("POL-003", "Classification & attributes", why)
    ok("POL-003", "Classification & attributes", why)

    # POL-010 stale or unverified evidence cannot be cited as authoritative
    if req.action == "cite_authoritative" or req.extra.get("authoritative_citation"):
        if req.extra.get("doc_status") != "current" or not req.extra.get("provenance"):
            return deny("POL-010", "Authoritative evidence", "Document is superseded or lacks a provenance hash.")
        ok("POL-010", "Authoritative evidence", "Document is current with provenance.")

    # POL-013 separation of duties and approver role
    if req.action == "approve":
        if not req.approval_id:
            return deny("POL-013", "Separation of duties", "No approval identifier supplied.")
        appr = _approval_state(req.approval_id)
        if not appr:
            return deny("POL-013", "Separation of duties", "Approval request does not exist.")
        if appr["requested_by"] == effective.id:
            return deny("POL-013", "Separation of duties", "The requester cannot approve their own request.")
        roles = APPROVER_ROLES.get(appr["kind"], set())
        if effective.role not in roles:
            return deny("POL-013", "Separation of duties", f"Role '{effective.role}' cannot approve '{appr['kind']}' requests.")
        ok("POL-013", "Separation of duties", "Approver differs from requester and holds an approver role.")

    # POL-005 consequential writes
    if req.action == "write":
        if not req.approval_id:
            return deny("POL-005", "Human approval for writes", "Writes require an approved human approval record.")
        appr = _approval_state(req.approval_id)
        if not appr or appr["status"] != "approved":
            return deny("POL-005", "Human approval for writes", "Approval is missing or not in 'approved' state.")
        if datetime.fromisoformat(appr["expires_at"]) < datetime.now(timezone.utc):
            return deny("POL-005", "Human approval for writes", "Approval has expired; request a new approval.")
        if not req.idempotency_key:
            return deny("POL-005", "Human approval for writes", "An idempotency key is required for writes.")
        if req.idempotency_key != appr["idempotency_key"]:
            return deny("POL-005", "Human approval for writes", "Idempotency key does not match the approved request.")
        if db.query_one("SELECT 1 FROM write_log WHERE idempotency_key = ?", (req.idempotency_key,)):
            return deny("POL-005", "Human approval for writes", "Replay detected: this approved write was already executed.")
        ok("POL-005", "Human approval for writes", "Valid, unexpired, unused approval with matching idempotency key.")

    return _finish("ALLOW", checks[-1].policy_id, "All applicable policy checks passed.")


def _record(d: Decision, on_behalf_of: Actor | None) -> None:
    with db.session(write=True) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM tool_invocations WHERE tool = ?", (d.request.tool or "",)
        ).fetchone()[0] if d.request.tool else None
        conn.execute(
            "INSERT INTO policy_decisions (id, ts, actor, role, action, resource, label, destination, tool, decision, "
            "policy_id, reason, checks_json, run_id, tool_invocations_after) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.id, d.ts, d.actor, d.role, d.request.action, d.request.resource, d.request.label, d.request.destination,
             d.request.tool, d.decision, d.policy_id, d.reason, db.jdump([c.as_dict() for c in d.checks]),
             d.request.run_id, count),
        )
        audit.append(
            d.actor,
            "policy.decision",
            f"{d.decision} {d.request.action} on {d.request.resource or '-'} ({d.policy_id})",
            {"decision_id": d.id, "decision": d.decision, "policy_id": d.policy_id, "reason": d.reason,
             "on_behalf_of": on_behalf_of.id if on_behalf_of else None, "run_id": d.request.run_id},
            conn,
        )


def list_decisions(decision: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql = "SELECT * FROM policy_decisions"
    params: list[Any] = []
    if decision:
        sql += " WHERE decision = ?"
        params.append(decision)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    out = db.query(sql, params)
    for r in out:
        r["checks"] = db.jload(r.pop("checks_json"), [])
    return out
