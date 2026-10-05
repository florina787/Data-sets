"""In-application Use Case Catalog (UC01–UC38, plus planned integrations).

Statuses are deliberately conservative: IMPLEMENTED means it runs end-to-end in this
repo (DEMO_MODE, synthetic data); PARTIAL means a real but limited implementation;
PLANNED means not implemented.
"""

from __future__ import annotations

_I, _P, _L = "IMPLEMENTED", "PARTIAL", "PLANNED"

_ROWS = [
    # id, name, stage, agent/engine, status, demo location, note
    ("UC01", "Requirement understanding", "Plan / Requirements", "Requirement Agent (deterministic parser)", _I, "Copilot, Requirements", ""),
    ("UC02", "Ambiguity detection", "Plan / Requirements", "Requirement Agent + ambiguity gate", _I, "Requirements", "CRITICAL ambiguity blocks workflow → human clarification"),
    ("UC03", "User-story generation", "Plan / Requirements", "Requirement Agent (template)", _I, "Requirements", ""),
    ("UC04", "Acceptance-criteria generation", "Plan / Requirements", "Requirement Agent (template)", _I, "Requirements", "Given/When/Then"),
    ("UC05", "Policy-to-requirement validation", "Plan / Requirements", "Policy Agent (BM25 RAG + checks)", _I, "Policy Evidence", "consistency / amendment / dependency findings"),
    ("UC06", "Application impact analysis", "Architecture / Impact", "Impact Agent", _I, "Impact Analysis", ""),
    ("UC07", "Microservice dependency analysis", "Architecture / Impact", "Impact Agent (dependency propagation)", _P, "Impact Analysis", "one-hop propagation over synthetic catalog"),
    ("UC08", "API impact analysis", "Architecture / Impact", "Impact Agent", _I, "Impact Analysis", ""),
    ("UC09", "Database/schema impact analysis", "Architecture / Impact", "Impact Agent", _I, "Impact Analysis", ""),
    ("UC10", "Architecture recommendation", "Architecture / Impact", "Architecture Agent (guardrailed)", _I, "Architecture", "KEEP/ENHANCE/ADD/REPLACE"),
    ("UC11", "Implementation-plan generation", "Development", "Developer Agent (template)", _I, "Development Plan", ""),
    ("UC12", "Code-change proposal", "Development", "Developer Agent (template)", _P, "Development Plan", "template patch for a synthetic repo; never merged"),
    ("UC13", "API/schema proposal", "Development", "Developer Agent (template)", _I, "Development Plan", ""),
    ("UC14", "Technical documentation generation", "Development", "Developer/Release Agents (template)", _P, "Development Plan, Release Center", "doc-update list + release notes only"),
    ("UC15", "Unit-test generation", "QA / Claim Simulation", "QA Agent", _I, "QA & Tests", "executed against the rules engine"),
    ("UC16", "API-test generation", "QA / Claim Simulation", "QA Agent", _P, "QA & Tests", "API test specs generated; not auto-executed"),
    ("UC17", "Regression-test selection", "QA / Claim Simulation", "Impact + QA Agents", _P, "Impact Analysis, QA & Tests", "indirect components flagged for regression scope; no optimisation"),
    ("UC18", "Boundary-test generation", "QA / Claim Simulation", "QA Agent", _I, "QA & Tests", "visit 10/11, annual max, effective date"),
    ("UC19", "Synthetic claim generation", "QA / Claim Simulation", "Seeded generator (deterministic)", _I, "Claims Simulation", "1k–100k claims"),
    ("UC20", "Historical/synthetic claims replay", "QA / Claim Simulation", "Simulator (shadow replay)", _I, "Claims Simulation, ClaimIQ", "synthetic replay only — no real history"),
    ("UC21", "Expected-vs-actual adjudication comparison", "QA / Claim Simulation", "Comparison engine", _I, "Claims Simulation", "expected vs UNEXPECTED change classification"),
    ("UC22", "PHI/privacy review", "Security / Governance", "Security Agent (rule-based)", _P, "Security & Governance", "advisory; not a compliance assessment"),
    ("UC23", "Security review", "Security / Governance", "Security Agent (rule-based)", _P, "Security & Governance", "advisory; no SAST/DAST"),
    ("UC24", "Governance evidence generation", "Security / Governance", "Governance Agent", _I, "Security & Governance", ""),
    ("UC25", "Audit/traceability review", "Security / Governance", "Audit log + traceability graph", _I, "Traceability, System Metrics", ""),
    ("UC26", "Release-risk scoring", "Release", "Release Agent (deterministic risk engine)", _I, "Release Center", ""),
    ("UC27", "Deployment-readiness assessment", "Release", "Release Agent", _I, "Release Center", "READY / READY WITH APPROVAL / NOT READY / BLOCKED"),
    ("UC28", "Release-note generation", "Release", "Release Agent (template)", _I, "Release Center", ""),
    ("UC29", "Rollback-plan generation", "Release", "Release Agent (template)", _I, "Release Center", ""),
    ("UC30", "Claim-denial monitoring", "ClaimIQ / Production", "ClaimIQ metrics", _I, "ClaimIQ", "SIMULATED production"),
    ("UC31", "Denial anomaly detection", "ClaimIQ / Production", "Statistical detector", _I, "ClaimIQ", "relative change + z-score"),
    ("UC32", "Claims anomaly detection", "ClaimIQ / Production", "Statistical detector", _P, "ClaimIQ", "denial & auth metrics alerted; latency/exceptions monitored only"),
    ("UC33", "Production incident investigation", "ClaimIQ / Production", "Root-Cause Agent", _I, "Root Cause", ""),
    ("UC34", "Root-cause analysis", "ClaimIQ / Production", "Root-Cause Agent (bounded loop)", _I, "Root Cause", ""),
    ("UC35", "Release-to-incident correlation", "ClaimIQ / Production", "Root-Cause Agent + correlation node", _I, "Root Cause", ""),
    ("UC36", "Requirement-to-defect traceability", "ClaimIQ / Production", "Traceability graph", _I, "Traceability", ""),
    ("UC37", "Remediation recommendation", "ClaimIQ / Production", "Remediation Agent (verified in simulation)", _I, "Root Cause", "never applied automatically"),
    ("UC38", "Regression-test generation from production failure", "ClaimIQ / Production", "Remediation + QA", _I, "Root Cause", "runnable pytest code"),
    ("UC39", "Defect sync to Jira / Azure DevOps", "Integrations", "Tracker adapter", _L, "-", "adapter interface only; not connected"),
    ("UC40", "FHIR Claim / ExplanationOfBenefit ingestion", "Integrations", "FHIR adapter", _L, "-", "mapping documented; not implemented"),
]

USE_CASES = [
    {"id": r[0], "use_case": r[1], "lifecycle_stage": r[2], "agent_engine": r[3], "status": r[4],
     "demo_available": r[4] != _L, "where": r[5], "note": r[6]}
    for r in _ROWS
]
