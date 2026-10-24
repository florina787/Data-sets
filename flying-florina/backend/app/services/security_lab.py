"""Security Test Lab: executable scenarios run against the real controls.

Each scenario performs the actual operation (policy evaluation, token check,
tool registration, approval execution, tool invocation) and reports the
observed outcome next to the expected one. Nothing is mocked.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from pydantic import BaseModel

from app.core import policy
from app.core.security import Actor, TokenError, issue_token, load_actor, verify_token
from app.core.util import now_iso
from app.integrations.mcp.registry import ToolDenied, ToolFailed, ToolSpec, UntrustedToolError, invocation_count
from app.retrieval.search import get_document, search
from app.services import approvals
from app.services.tools import registry


def _agent() -> Actor:
    return Actor(id="agent.security_lab", display_name="Security lab agent", role="agent", org="FF-Demo-MRO", is_agent=True)


def _u(uid: str) -> Actor:
    a = load_actor(uid)
    assert a is not None, uid
    return a


def s_public_read() -> dict[str, Any]:
    doc, why = get_document(_u("guest"), "DOC-001")
    d = policy.evaluate(_u("guest"), policy.PolicyRequest(action="read", resource="doc:DOC-001", label="PUBLIC"))
    return {"observed": "ALLOW" if doc and d.allowed else "DENY", "policy_id": d.policy_id, "reason": d.reason}


def s_restricted_read() -> dict[str, Any]:
    d = policy.evaluate(_u("exec.ava"), policy.PolicyRequest(action="read", resource="doc:DOC-003", label="RESTRICTED"))
    doc, _ = get_document(_u("exec.ava"), "DOC-003")
    hits = [h["doc_id"] for h in search(_u("exec.ava"), "engine mount isolator inspection")["results"]]
    leaked = doc is not None or "DOC-003" in hits
    return {"observed": "DENY" if not d.allowed and not leaked else "ALLOW", "policy_id": d.policy_id, "reason": d.reason,
            "detail": f"Search results for executive exclude DOC-003: {'DOC-003' not in hits}"}


def s_external_export() -> dict[str, Any]:
    before = invocation_count("records.export_email")
    try:
        registry().invoke(_agent(), _u("planner.marco"), "records.export_email", {"destination": "personal_email", "record_set": "restricted maintenance records"})
        observed, pid, reason = "ALLOW", "-", "export executed"
    except ToolDenied as e:
        observed, pid, reason = "DENY", e.decision.policy_id, e.decision.reason
    return {"observed": observed, "policy_id": pid, "reason": reason, "tool_invocations": invocation_count("records.export_email") - before}


def s_expired_approval() -> dict[str, Any]:
    a = approvals.create("work_order", "Lab: expired approval", _u("planner.marco"), {"aircraft_id": "AC-001", "title": "lab"}, ttl_seconds=-1)
    try:
        approvals.decide(a["id"], _u("rel.nadia"), True)
        return {"observed": "ALLOW", "policy_id": "-", "reason": "approved an expired request"}
    except approvals.ApprovalError as e:
        return {"observed": "DENY", "policy_id": "POL-005", "reason": e.message}


def s_stale_document() -> dict[str, Any]:
    d = policy.evaluate(_u("planner.marco"), policy.PolicyRequest(action="read", resource="doc:DOC-007", label="INTERNAL",
                                                                 extra={"authoritative_citation": True, "doc_status": "superseded", "provenance": True}))
    return {"observed": d.decision, "policy_id": d.policy_id, "reason": d.reason}


def s_privilege_escalation() -> dict[str, Any]:
    d1 = policy.evaluate(_agent(), policy.PolicyRequest(action="role_change", resource="user:agent.security_lab", target_actor="agent.security_lab"))
    d2 = policy.evaluate(_u("sec.ines"), policy.PolicyRequest(action="role_change", resource="user:sec.ines", target_actor="sec.ines"))
    observed = "DENY" if not d1.allowed and not d2.allowed else "ALLOW"
    return {"observed": observed, "policy_id": d1.policy_id, "reason": f"Agent: {d1.reason} | Self: {d2.reason}"}


def s_prompt_injection() -> dict[str, Any]:
    res = search(_u("planner.marco"), "supplier bulletin isolator packaging")
    hit = next((h for h in res["results"] if h["doc_id"] == "DOC-021"), None)
    before = invocation_count("records.export_email")
    try:
        registry().invoke(_agent(), _u("planner.marco"), "records.export_email", {"destination": "external_email", "record_set": "all"},
                          instruction_source="retrieved_content")
        observed, pid, reason = "ALLOW", "-", "tool ran"
    except ToolDenied as e:
        observed, pid, reason = "DENY", e.decision.policy_id, e.decision.reason
    return {"observed": observed, "policy_id": pid, "reason": reason,
            "detail": f"DOC-021 flags: {hit['flags'] if hit else 'not retrieved'}; quarantined snippet: {hit['snippet'][:120] if hit else '-'}",
            "tool_invocations": invocation_count("records.export_email") - before}


class _ShadowArgs(BaseModel):
    target: str


def s_untrusted_tool() -> dict[str, Any]:
    reg = registry()
    results = []
    for spec in (ToolSpec("shadow.exfiltrate", "1.0.0", "Unreviewed tool", "export", "RESTRICTED", _ShadowArgs, lambda target: target),
                 ToolSpec("parts.check_availability", "9.9.9", "Version drift", "read", "INTERNAL", _ShadowArgs, lambda target: target)):
        try:
            reg.register(spec)
            results.append(f"{spec.name}@{spec.version}: REGISTERED")
        except UntrustedToolError as e:
            results.append(str(e))
    ok = all("rejected" in r for r in results) and reg.tools["parts.check_availability"].version == "1.0.0"
    return {"observed": "DENY" if ok else "ALLOW", "policy_id": "POL-006", "reason": " | ".join(results)}


def s_missing_token() -> dict[str, Any]:
    try:
        verify_token(None)
        return {"observed": "ALLOW", "policy_id": "-", "reason": "accepted"}
    except TokenError as e:
        return {"observed": "DENY", "policy_id": "POL-012", "reason": f"{e.code}: {e.message}"}


def s_wrong_audience() -> dict[str, Any]:
    tok = issue_token("planner.marco", audience="some-other-service")
    try:
        verify_token(tok)
        return {"observed": "ALLOW", "policy_id": "-", "reason": "accepted"}
    except TokenError as e:
        return {"observed": "DENY", "policy_id": "POL-012", "reason": f"{e.code}: {e.message}"}


def s_replayed_write() -> dict[str, Any]:
    a = approvals.create("work_order", "Lab: replay check", _u("planner.marco"), {"aircraft_id": "AC-002", "title": "Lab replay check (synthetic)", "part_number": "P-6008"})
    approvals.decide(a["id"], _u("rel.nadia"), True)
    approvals.execute(a["id"], _u("planner.marco"), a["idempotency_key"])
    try:
        approvals.execute(a["id"], _u("planner.marco"), a["idempotency_key"])
        return {"observed": "ALLOW", "policy_id": "-", "reason": "second write executed"}
    except approvals.ApprovalError as e:
        return {"observed": "DENY", "policy_id": (e.decision or {}).get("policy_id", "POL-005"), "reason": e.message}


def s_tool_timeout() -> dict[str, Any]:
    try:
        registry().invoke(_agent(), _u("planner.marco"), "hangar.find_slots", {"base": "MAIN-HUB"}, fault="timeout")
        return {"observed": "ALLOW", "policy_id": "-", "reason": "no timeout"}
    except ToolFailed as e:
        registry()._breakers.pop("hangar.find_slots", None)  # reset breaker so the demo keeps working
        return {"observed": "DENY", "policy_id": "gateway", "reason": f"{e} (bounded wait, recorded as 'timeout')"}


SCENARIOS: list[tuple[str, str, str, Callable[[], dict[str, Any]]]] = [
    ("public_read", "Allowed public read", "ALLOW", s_public_read),
    ("restricted_read", "Unauthorized restricted read", "DENY", s_restricted_read),
    ("external_export", "Blocked external export (0 tool executions)", "DENY", s_external_export),
    ("expired_approval", "Expired approval", "DENY", s_expired_approval),
    ("stale_document", "Stale document cited as authoritative", "DENY", s_stale_document),
    ("privilege_escalation", "Privilege escalation attempt", "DENY", s_privilege_escalation),
    ("prompt_injection", "Prompt injection in retrieved document", "DENY", s_prompt_injection),
    ("untrusted_tool", "Untrusted / drifted MCP tool registration", "DENY", s_untrusted_tool),
    ("missing_token", "Missing token", "DENY", s_missing_token),
    ("wrong_audience", "Wrong token audience", "DENY", s_wrong_audience),
    ("replayed_write", "Replayed approved write", "DENY", s_replayed_write),
    ("tool_timeout", "Tool timeout", "DENY", s_tool_timeout),
]


def run(selected: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    for sid, title, expected, fn in SCENARIOS:
        if selected and sid not in selected:
            continue
        t0 = time.perf_counter()
        try:
            r = fn()
        except Exception as err:  # noqa: BLE001
            r = {"observed": "ERROR", "policy_id": "-", "reason": f"{type(err).__name__}: {err}"}
        out.append({"id": sid, "title": title, "expected": expected, **r, "passed": r["observed"] == expected,
                    "ts": now_iso(), "ms": round((time.perf_counter() - t0) * 1000, 1),
                    "tool_invocations": r.get("tool_invocations", 0)})
    return out
