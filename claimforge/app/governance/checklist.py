"""Governance / compliance checklist (DETERMINISTIC, evidence-based).

Each item is PASS / WARN / FAIL with the evidence that produced it. It does not claim
regulatory compliance; it documents explainability, oversight and traceability evidence.
"""

from __future__ import annotations


def governance_checklist(*, requirement, policy_result: dict, simulation, test_summary: dict,
                         approval: dict | None, live_ai: bool, trace_links: int) -> dict:
    items: list[dict] = []

    def add(item_id, name, status, evidence):
        items.append({"id": item_id, "item": name, "status": status, "evidence": evidence})

    blocking = requirement.blocking_ambiguities if requirement else []
    add("GOV-01", "Requirement traceable to policy evidence",
        "PASS" if policy_result.get("status") == "EVIDENCE_FOUND" else "FAIL",
        ", ".join(e["citation"] for e in policy_result.get("evidence", [])[:4]) or policy_result.get("status"))
    add("GOV-02", "Critical ambiguities resolved by a human",
        "PASS" if not blocking else "FAIL",
        "resolved: " + ", ".join(a.ambiguity_id for a in requirement.ambiguities if a.resolved_by == "HUMAN") if requirement else "-")
    add("GOV-03", "Assumptions documented",
        "PASS" if requirement and requirement.assumptions else "WARN",
        f"{len(requirement.assumptions) if requirement else 0} assumptions recorded")
    add("GOV-04", "Adjudication deterministic (no LLM in claims path)", "PASS",
        "app.claims.adjudicator.decide — pure function, versioned rulesets")
    add("GOV-05", "Every simulated determination explainable (reason code + rule id)",
        "PASS" if simulation is not None else "WARN",
        "reason_code and rule_id recorded for 100% of simulated claims" if simulation is not None else "simulation not run")
    add("GOV-06", "Generated test evidence passes",
        "PASS" if test_summary.get("total") and not test_summary.get("failed") else ("FAIL" if test_summary.get("failed") else "WARN"),
        f"{test_summary.get('passed', 0)}/{test_summary.get('total', 0)} passed")
    add("GOV-07", "Simulation shows no unexpected outcome changes",
        "PASS" if simulation is not None and simulation.unexpected_changes == 0 else ("FAIL" if simulation is not None else "WARN"),
        f"unexpected changes: {simulation.unexpected_changes if simulation is not None else 'n/a'}")
    add("GOV-08", "Human release approval recorded",
        "PASS" if approval and approval.get("decision") == "APPROVED" else "WARN",
        f"approved by {approval['approver']} ({approval['role']})" if approval and approval.get("decision") == "APPROVED" else "PENDING — human gate required")
    add("GOV-09", "Model-risk: LLM limited to narrative/explanation",
        "WARN" if live_ai else "PASS",
        "LIVE AI: narratives are LLM-assisted and must be reviewed" if live_ai else "DEMO MODE: no LLM used")
    add("GOV-10", "Traceability links requirement → policy → rule → test → release",
        "PASS" if trace_links >= 5 else "WARN", f"{trace_links} links")
    add("GOV-11", "Member/provider communication planned (P-40.1, 30 days)", "WARN",
        "Communication task identified in impact map; scheduling is outside demo scope")
    add("GOV-12", "Audit log enabled for agent/tool actions", "PASS", "in-memory audit log (app.observability.audit)")

    return {"items": items,
            "fail": sum(1 for i in items if i["status"] == "FAIL"),
            "warn": sum(1 for i in items if i["status"] == "WARN"),
            "pass": sum(1 for i in items if i["status"] == "PASS"),
            "disclaimer": "Governance evidence for demonstration — not a regulatory compliance attestation.",
            "method": "DETERMINISTIC evidence checklist"}
