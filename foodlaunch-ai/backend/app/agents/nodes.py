"""Agent nodes for the delivery and incident graphs.

DEMO mode agents are deterministic: rule-based analysis, seeded requirement
templates and seeded fixture patches. Patches really modify an isolated
candidate workspace, and every check is a real tool execution. Each activity
entry is labelled with its provenance.
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Any, TypedDict

from langgraph.types import interrupt

from app.agents import live
from app.db import kv_get, kv_set, new_id, now_iso, row, session
from app.errors import PlatformError
from app.records import activity
from app.services import delivery, incidents
from app.states import transition_run
from app.tools import inventory_sim, static_checks, testing, traffic, workspace

REPAIR_PATCHES = {"REG-001": "02-free-unit-recompute-fix.patch", "REG-002": "03-inventory-timeout-repair.patch"}
SYSTEM_ACTOR = "orchestrator"


def _append(left: list, right: list) -> list:
    return [*(left or []), *(right or [])]


class FlowState(TypedDict, total=False):
    run_id: str
    flow: str
    mode: str
    incident_id: str | None
    revision: str | None
    base_revision: str | None
    last_test_status: str | None
    last_failed_regressions: list[str]
    repair_attempts: int
    release_id: str | None
    outcome: str | None
    gate_ok: bool
    change_set_ids: Annotated[list[str], _append]
    test_run_ids: Annotated[list[str], _append]
    errors: Annotated[list[str], _append]


def _maybe_crash(node: str) -> None:
    """Test hook: FOODLAUNCH_CRASH_ONCE_AT=<node> simulates a process failure once."""
    target = os.environ.get("FOODLAUNCH_CRASH_ONCE_AT")
    if target == node and not kv_get(f"crash.{node}"):
        kv_set(f"crash.{node}", True)
        raise RuntimeError(f"Simulated interruption in {node}")


def _status(run_id: str) -> str:
    return delivery.get_run(run_id)["status"]


def _to(run_id: str, status: str, reason: str = "") -> None:
    if _status(run_id) != status:
        transition_run(run_id, status, SYSTEM_ACTOR, reason)


def _wait(run_id: str, stage: str, waiting_for: str, payload: dict) -> Any:
    delivery.set_stage(run_id, stage, waiting_for)
    value = interrupt({"waiting_for": waiting_for, **payload})
    delivery.set_stage(run_id, stage, None)
    return value


def _gate(run_id: str, stage: str, waiting_for: str, satisfied, payload: dict) -> bool:
    """Interrupt at most once per node execution; the graph loops back to the gate
    (a fresh execution) while the condition is unmet. Nodes re-run from the top on
    resume, so gates must not perform side effects before waiting."""
    if satisfied():
        return True
    _wait(run_id, stage, waiting_for, payload)
    return satisfied()


def route_gate(target: str, gate: str):
    return lambda state: target if state.get("gate_ok") else gate


# --- delivery flow ---------------------------------------------------------------------

def brief_analyst(state: FlowState) -> dict:
    run_id = state["run_id"]
    _maybe_crash("brief_analyst")
    delivery.set_stage(run_id, "brief_analysis")
    brief = delivery.current_brief(run_id)
    if state["mode"] == "live":
        analysis, usage = live.analyse_brief(run_id, brief["text"])
        items = [
            {"id": f"LQ-{i + 1}", "topic": a.topic, "question": a.question,
             "required": a.required_before_implementation, "blocks": "implementation",
             "options": a.options, "evidence": [], "policy_gap": None}
            for i, a in enumerate(analysis.ambiguities)
        ]
        payload, source, provenance = analysis.model_dump(), "live_ai", "live_ai"
        activity(run_id, "Brief Analyst", "llm_call", f"Live analysis by {usage['model']}: "
                 f"{len(items)} ambiguities", provenance, usage=usage)
    else:
        items = delivery.detect_ambiguities(brief["text"])
        text = brief["text"].lower()
        constraints = [c for k, c in [
            ("ontario", "Regional offer: Ontario"), ("while stock lasts", "Limited by available stock"),
            ("once per customer", "Per-customer limit"), ("weekend", "Time-boxed: one weekend"),
            ("free", "Free unit: zero-priced line item"),
        ] if k in text]
        payload = {"objective": brief["text"].split(":")[0].strip(), "constraints": constraints,
                   "stakeholders": ["Marketing (requester)", "Product owner", "Engineering",
                                    "Customer care (returns)", "Release approver"],
                   "method": "Deterministic checklist (9 promotion dimensions) + BM25 policy retrieval"}
        source, provenance = "deterministic", "deterministic"
    with session() as conn:
        conn.execute("UPDATE briefs SET analysis_json = ?, analysis_source = ? WHERE id = ?",
                     (json.dumps(payload), source, brief["id"]))
    delivery.store_clarifications(run_id, brief["version"], items, source)
    gaps = [i["id"] for i in items if i.get("policy_gap")]
    activity(run_id, "Brief Analyst", "analysis",
             f"Found {len(items)} ambiguities; {len(gaps)} have no policy answer ({', '.join(gaps) or 'none'})",
             provenance, ambiguities=[i["id"] for i in items])
    _to(run_id, "clarification-needed" if items else "requirements-review", "brief analysed")
    return {}


def clarification_gate(state: FlowState) -> dict:
    run_id = state["run_id"]
    pending = delivery.open_required_clarifications(run_id)
    ok = _gate(run_id, "clarification", "clarification_decisions",
               lambda: not delivery.open_required_clarifications(run_id), {"open": [p["id"] for p in pending]})
    if ok:
        activity(run_id, "Brief Analyst", "gate", "All required clarifications have recorded decisions",
                 "deterministic")
        _to(run_id, "requirements-review", "clarifications resolved")
    return {"gate_ok": ok}


def requirements_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    _maybe_crash("requirements_agent")
    delivery.set_stage(run_id, "requirements")
    brief = delivery.current_brief(run_id)
    if state["mode"] == "live":
        decisions = [c for c in delivery.list_clarifications(run_id) if c["status"] == "resolved"]
        result, usage = live.draft_requirements(run_id, brief["text"], decisions)
        reqs = [{"id": f"LREQ-{i + 1}", "title": r.title, "decisions": [],
                 "criteria": [{"id": f"LAC-{i + 1}.{j + 1}", "text": c.text, "critical": True}
                              for j, c in enumerate(r.criteria)]} for i, r in enumerate(result.requirements)]
        delivery.create_requirement_set(run_id, 1, brief["version"], "live AI draft from brief + decisions",
                                        "live_ai", reqs, [])
        activity(run_id, "Requirements Agent", "llm_call",
                 f"Live draft by {usage['model']}: {len(reqs)} requirements (not linked to executable tests)",
                 "live_ai", usage=usage)
    else:
        seed = delivery.scenario()["requirement_sets"][0]
        delivery.create_requirement_set(run_id, 1, brief["version"], seed["source"], "seeded_template",
                                        seed["requirements"], delivery.scenario()["test_plans"]["1"])
        acs = sum(len(r["criteria"]) for r in seed["requirements"])
        activity(run_id, "Requirements Agent", "requirements",
                 f"Drafted requirement set v1: {len(seed['requirements'])} requirements, {acs} acceptance "
                 "criteria, each linked to recorded decisions", "fixture")
    return {}


def requirements_gate(state: FlowState) -> dict:
    run_id = state["run_id"]
    version = delivery.requirement_set(run_id)["version"]
    ok = _gate(run_id, "requirements", "requirements_approval",
               lambda: delivery.requirement_set(run_id, version)["status"] == "approved", {"version": version})
    if ok:
        _to(run_id, "requirements-approved", f"requirement set v{version} approved")
    return {"gate_ok": ok}


def design_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    delivery.set_stage(run_id, "design")
    if not row("SELECT 1 FROM designs WHERE run_id = ?", (run_id,)):
        with session() as conn:
            conn.execute("INSERT INTO designs (id, run_id, content_json, source, created_at) VALUES (?, ?, ?, ?, ?)",
                         (new_id("DSN"), run_id, json.dumps(delivery.scenario()["design"]),
                          "fixture", now_iso()))
    activity(run_id, "Design Agent", "design", "Design recorded: 6 component changes, 3 API additions, 2 dependencies",
             "fixture")
    return {}


def implementation_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    delivery.set_stage(run_id, "implementation")
    if pending := delivery.open_required_clarifications(run_id):
        _to(run_id, "blocked", "implementation requires recorded decisions")
        raise PlatformError("Implementation blocked: required clarifications are open",
                            open=[p["id"] for p in pending])
    if state["mode"] == "live":
        _to(run_id, "blocked", "live patch execution disabled")
        activity(run_id, "Implementation Agent", "blocked",
                 "LIVE mode stops here. Live-generated patches are not executed because no container sandbox "
                 "is configured, and live requirements are not linked to the protected test suite. Use DEMO "
                 "mode for the end-to-end path.", "deterministic")
        return {"outcome": "blocked_live_execution_disabled"}
    _to(run_id, "implementing")
    current = delivery.current_release()
    base = current["revision"]
    workspace.create_workspace(run_id, base)
    patch_name = "01-campaign-implementation.patch"
    meta = delivery.scenario()["patches"][patch_name]
    _maybe_crash("implementation_agent")
    existing = row("SELECT * FROM change_sets WHERE run_id = ? AND patch_name = ?", (run_id, patch_name))
    if existing:
        cs_id, revision = existing["id"], existing["revision"]
    else:
        applied = workspace.apply_patch(run_id, workspace.load_fixture_patch(patch_name),
                                        f"{meta['title']} [{run_id}]")
        cs_id = delivery.record_change_set(run_id, "implementation", patch_name, applied, meta)
        revision = applied.revision
    activity(run_id, "Implementation Agent", "patch",
             f"Fixture proposal applied in isolated workspace: {meta['title']} -> {revision[:10]}",
             "fixture", change_set=cs_id, revision=revision)
    return {"revision": revision, "base_revision": base, "change_set_ids": [cs_id]}


def qa_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    _to(run_id, "testing")
    delivery.set_stage(run_id, "testing")
    req_set = delivery.approved_set(run_id)
    result = testing.run_acceptance(run_id=run_id, revision=state["revision"], suite_version=req_set["version"],
                                    plan=req_set["test_plan"], purpose=f"candidate {state['flow']}")
    failed_regressions = sorted({rid for r in delivery.test_results(result["id"]) if r["outcome"] != "passed"
                                 for rid in r["regression_ids"]})
    results = delivery.test_results(result["id"])
    failing_unmarked = [n for n in result["failed"]
                        if not any(r["nodeid"] == n and r["regression_ids"] for r in results)]
    activity(run_id, "QA Agent", "test_run",
             f"pytest exit {result['exit_code']}: {result['passed']}/{result['total']} passed on "
             f"{state['revision'][:10]}" + (f"; failing: {', '.join(result['failed'])}" if result["failed"] else ""),
             "tool", test_run=result["id"])
    return {"last_test_status": result["status"], "test_run_ids": [result["id"]],
            "last_failed_regressions": failed_regressions + (["UNMAPPED"] if failing_unmarked else [])}


def route_after_qa(state: FlowState) -> str:
    if state.get("last_test_status") == "passed":
        return "review_agent"
    failed = state.get("last_failed_regressions") or []
    if (state.get("repair_attempts", 0) < 1 and failed and "UNMAPPED" not in failed
            and all(f in REPAIR_PATCHES for f in failed)):
        return "repair_agent"
    return "blocked"


def repair_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    _to(run_id, "implementing", "repair of failing regression test")
    delivery.set_stage(run_id, "repair")
    failed = state.get("last_failed_regressions") or []
    patch_name = REPAIR_PATCHES[failed[0]]
    meta = delivery.scenario()["patches"][patch_name]
    existing = row("SELECT * FROM change_sets WHERE run_id = ? AND patch_name = ?", (run_id, patch_name))
    if existing:
        cs_id, revision = existing["id"], existing["revision"]
    else:
        applied = workspace.apply_patch(run_id, workspace.load_fixture_patch(patch_name),
                                        f"{meta['title']} [{run_id}]")
        cs_id = delivery.record_change_set(run_id, "repair", patch_name, applied, meta, state.get("incident_id"))
        revision = applied.revision
    activity(run_id, "Repair Agent", "patch",
             f"Fixture proposal for {failed[0]}: {meta['title']} -> {revision[:10]}. "
             "The protected regression test is re-run unchanged.", "fixture", change_set=cs_id)
    return {"revision": revision, "change_set_ids": [cs_id], "repair_attempts": state.get("repair_attempts", 0) + 1}


def blocked(state: FlowState) -> dict:
    run_id = state["run_id"]
    if state.get("last_test_status") == "passed":
        reason = "release evidence incomplete (see release gates)"
    elif "UNMAPPED" in (state.get("last_failed_regressions") or []):
        reason = "failing tests are not covered by a known bounded repair; human investigation needed"
    else:
        reason = f"tests still failing after {state.get('repair_attempts', 0)} bounded repair attempt(s)"
    _to(run_id, "blocked", reason)
    activity(run_id, "QA Agent", "blocked", f"Run blocked: {reason}", "deterministic")
    return {"outcome": "blocked"}


def review_agent(state: FlowState) -> dict:
    run_id = state["run_id"]
    delivery.set_stage(run_id, "review")
    results = static_checks.run_static_checks(run_id, state["revision"])
    for r in results:
        if r["status"] != "passed":
            delivery.add_finding(run_id, state["revision"], "high", True, f"{r['tool']} failed",
                                 f"{len(r['findings'])} findings", r["tool"])
    activity(run_id, "Review Agent", "static_checks",
             "; ".join(f"{r['tool']}: {r['status']} (exit {r['exit_code']}, {len(r['findings'])} findings)"
                       for r in results) + ". Automated checks only, not a security certification.", "tool")
    return {}


def release_coordinator(state: FlowState) -> dict:
    run_id = state["run_id"]
    delivery.set_stage(run_id, "release")
    kind = "repair" if state["flow"] == "incident" else "feature"
    release = delivery.create_release(run_id, state["revision"], SYSTEM_ACTOR, kind, state.get("incident_id"))
    gates = delivery.evaluate_gates(run_id, state["revision"])
    failing = [g["id"] for g in gates["gates"] if not g["passed"]]
    _to(run_id, "awaiting-release-approval" if not failing else "blocked", "release gates evaluated")
    activity(run_id, "Release Coordinator", "gates",
             f"Evidence {'ready' if not failing else 'incomplete: ' + ', '.join(failing)}; manifest "
             f"{release['manifest_hash'][:12]} for {state['revision'][:10]}. A human approver must authorise it.",
             "deterministic", release_id=release["id"])
    return {"release_id": release["id"]}


def route_after_release(state: FlowState) -> str:
    return "approval_gate" if delivery.get_release(state["release_id"])["status"] == "awaiting-approval" else "blocked"


def approval_gate(state: FlowState) -> dict:
    run_id = state["run_id"]

    def settled() -> bool:
        return delivery.get_release(state["release_id"])["status"] in ("deployed", "failed", "invalidated")

    ok = _gate(run_id, "release", "release_approval_and_deploy", settled, {"release_id": state["release_id"]})
    if not ok:
        return {"gate_ok": False}
    release = delivery.get_release(state["release_id"])
    activity(run_id, "Release Coordinator", "deployment", f"Release {release['id']} is {release['status']}", "tool")
    return {"gate_ok": True, "outcome": release["status"]}


def post_deploy_check(state: FlowState) -> dict:
    run_id = state["run_id"]
    if state.get("outcome") != "deployed":
        return {}
    report = traffic.generate(1, run_id=run_id)
    activity(run_id, "Release Coordinator", "smoke_test",
             f"Post-deploy smoke journey on {str(report['revision'])[:10]}: {report['outcomes']}", "tool")
    return {}


# --- incident flow ---------------------------------------------------------------------

def incident_analyst(state: FlowState) -> dict:
    run_id = state["run_id"]
    incident = incidents.get_incident(state["incident_id"])
    analysis = incident["analysis"]
    activity(run_id, "Incident Analyst", "analysis",
             f"{incident['id']}: {len(analysis['evidence'])} evidence items and "
             f"{len(analysis['hypotheses'])} hypotheses. "
             "Scripted fault demonstration.", "deterministic", incident_id=incident["id"])
    return {"revision": incident["revision"]}


def requirements_update(state: FlowState) -> dict:
    run_id = state["run_id"]
    seed = delivery.scenario()["requirement_sets"]
    v1 = seed[0]["requirements"]
    v2 = v1 + seed[1]["adds"]
    brief = delivery.current_brief(run_id)
    delivery.create_requirement_set(run_id, 2, brief["version"], seed[1]["source"], "incident",
                                    v2, delivery.scenario()["test_plans"]["2"], state["incident_id"])
    if _status(run_id) in ("deployed", "rolled-back"):
        _to(run_id, "requirements-review", f"incident {state['incident_id']}")
    activity(run_id, "Incident Analyst", "requirements",
             "Proposed requirement set v2: adds REQ-9 (fail fast on inventory unavailability) with regression "
             "REG-002. Needs product-owner approval.", "fixture")
    return {}


def reproduce(state: FlowState) -> dict:
    """Run the new regression suite on the released revision to confirm the failure (evidence)."""
    run_id = state["run_id"]
    req_set = delivery.approved_set(run_id)
    incident = incidents.get_incident(state["incident_id"])
    result = testing.run_acceptance(run_id=run_id, revision=incident["revision"], suite_version=req_set["version"],
                                    plan=req_set["test_plan"], purpose="reproduce incident on released revision")
    workspace.reset_workspace_to(run_id, incident["revision"])
    activity(run_id, "QA Agent", "test_run",
             f"Reproduction on released {incident['revision'][:10]}: exit {result['exit_code']}, "
             f"failing {', '.join(result['failed']) or 'none'}", "tool", test_run=result["id"])
    failed = sorted({rid for r in delivery.test_results(result["id"]) if r["outcome"] != "passed"
                     for rid in r["regression_ids"]})
    return {"test_run_ids": [result["id"]], "last_failed_regressions": failed, "last_test_status": result["status"],
            "repair_attempts": 0}


def route_after_reproduce(state: FlowState) -> str:
    failed = state.get("last_failed_regressions") or []
    return "repair_agent" if failed and all(f in REPAIR_PATCHES for f in failed) else "blocked"


def verify_under_fault(state: FlowState) -> dict:
    run_id = state["run_id"]
    incident_id = state["incident_id"]
    if state.get("outcome") != "deployed":
        return {}
    fault_active = inventory_sim.fault_state().get("active")
    report = traffic.generate(2, run_id=run_id)
    graceful = (fault_active and set(report["outcomes"]) == {"checkout_503"}
                and all(report["carts_preserved_after_failure"]))
    activity(run_id, "Incident Analyst", "verification",
             f"Under {'active' if fault_active else 'no'} fault: outcomes {report['outcomes']}, "
             f"max checkout {report['max_checkout_ms']} ms, carts preserved "
             f"{report['carts_preserved_after_failure']}", "tool")
    if graceful:
        incidents.set_status(incident_id, "mitigated", SYSTEM_ACTOR, "fail-fast verified under fault")
    return {}


def fault_gate(state: FlowState) -> dict:
    ok = _gate(state["run_id"], "recovery", "fault_cleared", lambda: not inventory_sim.fault_state().get("active"),
               {"incident_id": state["incident_id"]})
    return {"gate_ok": ok}


def verify_after_clear(state: FlowState) -> dict:
    run_id = state["run_id"]
    incident_id = state["incident_id"]
    if state.get("outcome") != "deployed":
        return {}
    report = traffic.generate(2, run_id=run_id)
    recovered = set(report["outcomes"]) == {"order_created"}
    activity(run_id, "Incident Analyst", "verification",
             f"After fault cleared: outcomes {report['outcomes']} -> "
             f"{'recovery verified' if recovered else 'NOT recovered'}", "tool")
    if recovered:
        incidents.set_status(incident_id, "resolved", SYSTEM_ACTOR, "checkout recovered after fault cleared")
    return {"outcome": "recovered" if recovered else "not_recovered"}
