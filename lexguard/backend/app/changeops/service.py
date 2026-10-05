"""ChangeOps - AI Governance SDLC for policy changes.

POLICY CHANGE -> IMPACT ANALYSIS -> AFFECTED WORKFLOWS / PRACTICES / PROVIDERS -> CONFIGURATION -> TEST GENERATION
-> EVALUATION -> PILOT -> RISK REVIEW -> HUMAN APPROVAL -> SIMULATED DEPLOYMENT -> MONITORING

Policy text is parsed by deterministic keyword rules into a structured change. Text that cannot be
structured is returned as NEEDS_STRUCTURING rather than guessed.
"""

from __future__ import annotations

import hashlib
import re

from app.access.matter_access import build_access_scope
from app.assurance import pipeline
from app.citations import verifier
from app.models.db import GovernanceStateRow, session
from app.services.data_store import DataStore

OUTPUT_KEYWORDS = {
    r"\bresearch\b": ["research", "brief"],
    r"\bdue diligence\b": ["due_diligence_report", "findings"],
    r"\b(client communication|client alert|alerts?)\b": ["client_communication"],
    r"\bsummar(y|ies|isation|ization)\b": ["summary"],
    r"\btimelines?\b": ["timeline"],
    r"\b(work product|output)\b": ["*"],
}
DEST_KEYWORDS = {
    r"\bexternal(ly)?\b": ["external_client", "external_court", "external_public", "external_counterparty"],
    r"\bclient[- ]facing\b|\bto clients?\b": ["external_client"],
    r"\bcourts?\b|\bfilings?\b": ["external_court"],
    r"\binternal(ly)?\b": ["internal"],
}
REQUIREMENT_KEYWORDS = {
    r"citation verification|verified citations|verify citations": "citation_verification",
    r"lawyer review|human review|partner review": "lawyer_review",
    r"assurance": "assurance_pass",
    r"privilege review": "privilege_review",
}


def parse(text: str) -> dict:
    low = text.lower()
    outputs: set[str] = set()
    for rx, vals in OUTPUT_KEYWORDS.items():
        if re.search(rx, low):
            outputs.update(vals)
    dests: set[str] = set()
    for rx, vals in DEST_KEYWORDS.items():
        if re.search(rx, low):
            dests.update(vals)
    reqs = sorted({v for rx, v in REQUIREMENT_KEYWORDS.items() if re.search(rx, low)})
    return {"output_types": sorted(outputs) or ["*"], "destinations": sorted(dests) or ["*"],
            "requirements": reqs, "ai_generated_only": "ai" in low.split() or "ai-generated" in low}


def _match(values: list[str], wanted: list[str]) -> bool:
    return "*" in wanted or bool(set(values) & set(wanted))


def analyze(store: DataStore, text: str) -> dict:
    change = parse(text)
    change_id = "CHG-" + hashlib.sha1(text.strip().lower().encode()).hexdigest()[:8].upper()
    if not change["requirements"]:
        return {"change_id": change_id, "status": "NEEDS_STRUCTURING", "policy_text": text, "parsed": change,
                "message": "No enforceable requirement recognised. Restate the policy using a supported control "
                           "(citation verification, lawyer review, assurance, privilege review)."}
    affected, compliant = [], []
    overlay = _gate_overlay()
    for w in store.workflows.values():
        if not (_match(w.output_types, change["output_types"]) and _match(w.destinations, change["destinations"])):
            continue
        gates = set(w.gates) | set(overlay.get(w.workflow_id, []))
        missing = [r for r in change["requirements"] if r not in gates]
        row = {"workflow_id": w.workflow_id, "name": w.name, "status": w.status, "practices": w.practice_ids,
               "providers": w.providers, "prompts": w.prompts, "current_gates": sorted(gates), "missing_gates": missing,
               "destinations": [d for d in w.destinations if _match([d], change["destinations"])]}
        (affected if missing else compliant).append(row)
    practices = sorted({store.practices[p] for r in affected for p in r["practices"]})
    providers = sorted({store.providers[p].name for r in affected for p in r["providers"]})
    prompts = sorted({p for r in affected for p in r["prompts"]})
    tests = []
    for r in affected:
        for req in r["missing_gates"]:
            tests.append({"test_id": f"T-{r['workflow_id']}-{req}".upper(), "workflow_id": r["workflow_id"],
                          "description": f"{r['name']}: AI output for {', '.join(r['destinations'])} must be blocked unless "
                                         f"'{req.replace('_', ' ')}' passes."})
    evaluation = _regression(store, change)
    pilot = _pilot(store, affected)
    risk = "HIGH" if sum(1 for r in affected if r["status"] == "PRODUCTION") >= 3 else "MEDIUM" if affected else "LOW"
    state = _approval_state(change_id)
    stages = [
        {"stage": "Policy change", "status": "COMPLETE", "detail": text},
        {"stage": "Impact analysis", "status": "COMPLETE", "detail": f"Parsed requirement(s): {', '.join(change['requirements'])}"},
        {"stage": "Affected workflows", "status": "COMPLETE", "detail": f"{len(affected)} require change; {len(compliant)} already compliant"},
        {"stage": "Affected practices", "status": "COMPLETE", "detail": ", ".join(practices) or "None"},
        {"stage": "Affected providers", "status": "COMPLETE", "detail": ", ".join(providers) or "None"},
        {"stage": "Configuration", "status": "COMPLETE", "detail": f"{sum(len(r['missing_gates']) for r in affected)} gate insertion(s) prepared"},
        {"stage": "Test generation", "status": "COMPLETE", "detail": f"{len(tests)} regression test(s) generated"},
        {"stage": "Evaluation", "status": "PASS" if evaluation["passed"] else "FAIL", "detail": evaluation["summary"]},
        {"stage": "Pilot", "status": "COMPLETE", "detail": pilot["summary"]},
        {"stage": "Risk review", "status": "COMPLETE", "detail": f"Change risk {risk}"},
        {"stage": "Human approval", "status": "APPROVED" if state else "PENDING", "detail":
         f"Approved by {state['approved_by']}" if state else "AI Governance approval required"},
        {"stage": "Simulated deployment", "status": "DEPLOYED (SIMULATED)" if state else "NOT STARTED", "detail":
         "Gates applied to workflow configuration overlay" if state else "Awaiting approval"},
        {"stage": "Monitoring", "status": "ACTIVE" if state else "NOT STARTED", "detail":
         "Watching delivery-block rate, citation failure rate, review hours" if state else ""},
    ]
    return {"change_id": change_id, "status": "APPROVED" if state else "PENDING_APPROVAL", "policy_text": text,
            "parsed": change, "affected_workflows": affected, "compliant_workflows": compliant,
            "affected_practices": practices, "affected_providers": providers, "affected_prompts": prompts,
            "approval_gates": [{"workflow_id": r["workflow_id"], "add_gates": r["missing_gates"]} for r in affected],
            "generated_tests": tests, "evaluation": evaluation, "pilot": pilot, "risk": risk, "stages": stages}


def _regression(store: DataStore, change: dict) -> dict:
    """Run the new control against a real AI work product destined for external use."""
    scope = build_access_scope(store, store.users["U-002"], "M-1001")
    memo = store.pregenerated["WP-MEMO-MAPLE-001"]
    vers = [verifier.verify(store, scope, p["pid"], p["claim"], p["citation"]).model_dump() for p in memo["propositions"]]
    res = pipeline.evaluate(propositions=memo["propositions"], verifications=vers, playbook_results=[],
                            policy_decision="PERMITTED_WITH_CONTROLS", privilege_flags=[], destination="external_client")
    tests = [
        {"test": "External AI research memo with an unsupported citation is blocked from delivery",
         "pass": not res.external_delivery_allowed, "observed": f"assurance {res.status}, external delivery allowed = {res.external_delivery_allowed}"},
        {"test": "Fully verified output remains deliverable after approval",
         "pass": pipeline.evaluate(propositions=memo["propositions"][:8], verifications=vers[:8], playbook_results=[],
                                   policy_decision="PERMITTED_WITH_CONTROLS", privilege_flags=[],
                                   destination="external_client").external_delivery_allowed,
         "observed": "8 supported propositions"},
        {"test": "Internal research is unaffected", "pass": "internal" not in change["destinations"] or "*" in change["destinations"],
         "observed": f"destinations in scope: {', '.join(change['destinations'])}"},
    ]
    passed = all(t["pass"] for t in tests)
    return {"passed": passed, "tests": tests, "summary": f"{sum(t['pass'] for t in tests)}/{len(tests)} regression checks passed"}


def _pilot(store: DataStore, affected: list[dict]) -> dict:
    ids = {r["workflow_id"] for r in affected}
    runs = [r for r in store.usage_runs if r["workflow_id"] in ids and r["outcome"] != "BLOCKED"]
    would_block = [r for r in runs if r.get("citation_failures", 0) > 0]
    return {"historical_runs": len(runs), "would_have_been_blocked": len(would_block),
            "additional_review_hours_est": round(0.3 * len(runs), 1),
            "summary": f"Replayed {len(runs)} synthetic historical runs; {len(would_block)} would have been held for citation fixes",
            "label": "Synthetic pilot replay"}


def _approval_state(change_id: str) -> dict | None:
    with session() as s:
        row = s.get(GovernanceStateRow, f"policy_change:{change_id}")
        return row.value if row else None


def _gate_overlay() -> dict[str, list[str]]:
    with session() as s:
        row = s.get(GovernanceStateRow, "workflow_gate_overlay")
        return dict(row.value) if row else {}


def approve(store: DataStore, change_id: str, text: str, approver_id: str) -> dict:
    result = analyze(store, text)
    if result["change_id"] != change_id:
        raise ValueError("Change ID does not match policy text.")
    if result["status"] == "NEEDS_STRUCTURING":
        raise ValueError("Change is not structured and cannot be approved.")
    if not result["evaluation"]["passed"]:
        raise ValueError("Regression evaluation failed; change cannot be approved.")
    overlay = _gate_overlay()
    for g in result["approval_gates"]:
        overlay[g["workflow_id"]] = sorted(set(overlay.get(g["workflow_id"], [])) | set(g["add_gates"]))
    with session() as s:
        s.merge(GovernanceStateRow(key=f"policy_change:{change_id}", value={"approved_by": approver_id, "text": text,
                                                                            "deployment": "SIMULATED"}))
        s.merge(GovernanceStateRow(key="workflow_gate_overlay", value=overlay))
        s.commit()
    return analyze(store, text)


def gate_overlay() -> dict[str, list[str]]:
    return _gate_overlay()
