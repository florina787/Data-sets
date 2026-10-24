"""Static catalogs: personas, agents, compliance mapping, connector status, API/MCP comparison."""

from __future__ import annotations

import time
from typing import Any

from app.core import db
from app.core.config import get_settings

PERSONAS = [
    {"user_id": "exec.ava", "persona": "Executive", "role": "executive", "focus": "Value, risk, roadmap", "default_page": "/executive"},
    {"user_id": "planner.marco", "persona": "Maintenance Planner", "role": "maintenance_planner", "focus": "Plans, parts, approvals", "default_page": "/aog"},
    {"user_id": "tech.jun", "persona": "Technician", "role": "technician", "focus": "Task cards, evidence", "default_page": "/maintenance"},
    {"user_id": "rel.nadia", "persona": "Reliability Engineer", "role": "reliability_engineer", "focus": "Trends, hypotheses, approvals", "default_page": "/fleet"},
    {"user_id": "arch.olu", "persona": "Enterprise Architect", "role": "enterprise_architect", "focus": "Legacy X-Ray, bridges", "default_page": "/legacy"},
    {"user_id": "sec.ines", "persona": "Security Officer", "role": "security_officer", "focus": "Policies, kill switch, audit", "default_page": "/trust"},
    {"user_id": "audit.kai", "persona": "Auditor", "role": "auditor", "focus": "Evidence, audit export", "default_page": "/compliance"},
    {"user_id": "fde.sam", "persona": "Forward Deployed Engineer", "role": "fde", "focus": "Bridges, demos, pilots", "default_page": "/bridge"},
    {"user_id": "guest", "persona": "Guest", "role": "guest", "focus": "Read-only PUBLIC data", "default_page": "/"},
    {"user_id": "supplier.lee", "persona": "Guest (external supplier)", "role": "guest", "focus": "External org - mostly denied", "default_page": "/"},
]

AGENTS = [
    ("Intake & Intent Agent", "Deterministic routing and input normalization; asks for clarification when ambiguous.", []),
    ("Supervisor Agent", "DAG planning, state transitions, retries, cancellation, parallel waves.", []),
    ("Asset Telemetry Agent", "Time-series statistics, outliers, data-quality checks.", ["telemetry.get_series"]),
    ("Diagnostic Evidence Agent", "Hypotheses with supporting/contradicting evidence; never a diagnosis.", ["maintenance.get_history"]),
    ("Knowledge Retrieval Agent", "Access-filtered hybrid search with citations and injection quarantine.", ["docs.search"]),
    ("Parts Agent", "Reconciled inventory, approved alternates, supplier lead times.", ["parts.check_availability"]),
    ("Maintenance Planner Agent", "Qualified technicians, hangar slots, dry-run drafts.", ["roster.find_qualified", "hangar.find_slots", "workorder.create_draft"]),
    ("Compliance Agent", "Evidence sufficiency checklist (not certification).", ["docs.search"]),
    ("Legacy Discovery Agent", "Parses metadata, builds dependency graph and inventory.", []),
    ("Integration Architect Agent", "Compares REST/OData/events/batch/facade/MCP; generates adapters.", []),
    ("Security & Governance Agent", "Explains deterministic policy decisions; never overrides them.", []),
    ("Scenario Simulator Agent", "Deterministic scenarios, seeded Monte Carlo, sensitivity, ROI.", []),
    ("Reporting Agent", "Composes workspaces, citations and exportable reports.", []),
]

COMPLIANCE = [
    {"control": "Deny-by-default RBAC/ABAC per endpoint and tool", "implementation": "app/core/policy.py POL-001/002/003; tests", "status": "implemented (demo)",
     "references": ["NIST SP 800-171 3.1.1-3.1.3", "NIST AI RMF GOVERN 1.4"]},
    {"control": "Separation of duties for approvals", "implementation": "POL-013; approvals service", "status": "implemented (demo)",
     "references": ["NIST SP 800-171 3.1.4"]},
    {"control": "Least privilege for agents", "implementation": "Agent rights = intersection with requesting human", "status": "implemented (demo)",
     "references": ["NIST SP 800-171 3.1.5", "NIST AI RMF MAP 3.5"]},
    {"control": "Audit logging with integrity verification", "implementation": "Hash-chained audit_events + verifier", "status": "partial (tamper-evident only)",
     "references": ["NIST SP 800-171 3.3.1, 3.3.8"]},
    {"control": "Identification and authentication", "implementation": "Signed demo session tokens; audience/expiry checks", "status": "demo only - requires enterprise IdP + MFA",
     "references": ["NIST SP 800-171 3.5.1-3.5.3"]},
    {"control": "Boundary protection / no exfiltration", "implementation": "POL-004 + OFFLINE_MODE egress guard", "status": "implemented (process level)",
     "references": ["NIST SP 800-171 3.13.1"]},
    {"control": "Human oversight of consequential AI actions", "implementation": "Approval gate, dry-run drafts, execution-time policy check", "status": "implemented (demo)",
     "references": ["NIST AI RMF MANAGE 2.4", "NIST AI RMF GOVERN 3.2"]},
    {"control": "Prompt injection handling", "implementation": "Retrieval sanitization + POL-011", "status": "implemented (pattern-based, not exhaustive)",
     "references": ["OWASP LLM01", "NIST AI RMF MEASURE 2.7"]},
    {"control": "Incident response / kill switch", "implementation": "POL-009 kill switch cancels workflows", "status": "implemented (demo)",
     "references": ["NIST SP 800-171 3.6.1", "NIST AI RMF MANAGE 2.3"]},
    {"control": "CMMC level mapping", "implementation": "Configurable reference only", "status": "not assessed",
     "references": ["CMMC model (version configurable; verify current program rules)"]},
    {"control": "ITAR/EAR applicability screening", "implementation": "Informational checklist DOC-018; no controlled data ingested", "status": "informational only",
     "references": ["ITAR/EAR - requires qualified export-compliance review"]},
    {"control": "Privacy / contractual data handling", "implementation": "Synthetic data only; redaction in logs", "status": "partial",
     "references": ["Contractual clauses (customer-specific)"]},
]

INTEGRATION_MATRIX = [
    {"approach": "Direct API (REST/OData)", "use_cases": "Transactional reads/writes through documented interfaces", "strengths": "Governed, versioned, supported",
     "limitations": "Requires access, scopes, vendor docs", "risks": "Over-broad scopes; undocumented endpoints", "recommendation": "Default for system-to-system integration"},
    {"approach": "MCP tool", "use_cases": "Agent access to narrow, read-only capabilities", "strengths": "Discoverable, schema-typed for agents",
     "limitations": "Not an API governance layer; trust depends on the backing API", "risks": "Tool spoofing, over-permissioned tools", "recommendation": "Thin facade over an already secured API; pin and allowlist"},
    {"approach": "Events / CDC", "use_cases": "Near-real-time state propagation", "strengths": "Decoupled, fresh data",
     "limitations": "Ordering, replay, schema evolution", "risks": "Consistency gaps; unauthorized capture", "recommendation": "Only when permitted and tables have stable keys"},
    {"approach": "Batch / file bridge", "use_cases": "Legacy nightly exports", "strengths": "Works with any legacy system",
     "limitations": "Latency; data quality", "risks": "Silent bad loads", "recommendation": "Validate, quarantine, reconcile, audit"},
    {"approach": "RAG over documents", "use_cases": "Procedures, bulletins, evidence", "strengths": "Answers with citations",
     "limitations": "Only as good as metadata", "risks": "Prompt injection; stale revisions; leakage", "recommendation": "Filter by classification before ranking; cite revisions"},
]


def connectors() -> list[dict[str, Any]]:
    s = get_settings()
    llm = {"status": "disabled", "detail": "LLM_ENABLED=false. Deterministic rules engine is used."}
    if s.llm_enabled:
        llm = detect_llm()
    apps = db.query("SELECT id, name, kind FROM applications ORDER BY id")
    out = [{"id": a["id"], "name": a["name"], "kind": a["kind"], "status": "simulated", "detail": "Synthetic fixture; no live system."} for a in apps]
    out += [
        {"id": "IFS-CLOUD", "name": "IFS Cloud (customer instance)", "kind": "erp", "status": "not_connected",
         "detail": "Planned. Requires customer-provided access to documented, licensed REST/OData projections. Never assumed."},
        {"id": "MCP-DEMO", "name": "Demo maintenance MCP server (stdio)", "kind": "mcp", "status": "local", "detail": "mcp_servers/demo_maintenance; test via Bridge Studio."},
        {"id": "LLM", "name": "Optional local LLM (Ollama/llama.cpp)", "kind": "llm", **llm},
        {"id": "POSTGRES", "name": "PostgreSQL (optional)", "kind": "database", "status": "planned", "detail": "SQLite is used; PostgreSQL profile not implemented."},
    ]
    return out


def detect_llm() -> dict[str, Any]:
    """Probe the optional local model endpoint (loopback only, policy POL-008)."""
    s = get_settings()
    if not (s.llm_url.startswith("http://127.0.0.1") or s.llm_url.startswith("http://localhost")):
        return {"status": "blocked", "detail": "LLM_URL is not loopback; denied by POL-008."}
    import httpx

    t0 = time.perf_counter()
    try:
        r = httpx.get(f"{s.llm_url}/api/tags", timeout=1.0)
        models = [m.get("name") for m in r.json().get("models", [])]
        return {"status": "available", "detail": f"{len(models)} local model(s): {', '.join(models[:5])}", "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as err:  # noqa: BLE001
        return {"status": "not_detected", "detail": f"No local model server at {s.llm_url} ({type(err).__name__}). Rules engine in use."}
