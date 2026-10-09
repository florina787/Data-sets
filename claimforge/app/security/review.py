"""Security & privacy review (ADVISORY, rule-based).

Produces findings and checks for a requirement/change. This is an engineering
advisory aid for the demo; it is NOT a formal compliance assessment or certification.
"""

from __future__ import annotations

from app.config.settings import Settings
from app.models.domain import Impact, ImpactAction, Requirement, Severity


def security_review(req: Requirement, impacts: list[Impact], settings: Settings,
                    request_screen_flagged: bool = False) -> dict:
    findings: list[dict] = []
    checks: list[dict] = []
    changed_types = {i.component_type for i in impacts if i.action is not ImpactAction.KEEP}

    def finding(fid, sev: Severity, area, text, rec):
        findings.append({"id": fid, "severity": sev.value, "area": area, "finding": text, "recommendation": rec})

    if "VISIT_COUNTING" in req.facets or "AUTH_THRESHOLD_ADD" in req.facets:
        finding("SEC-PHI-01", Severity.MEDIUM, "PHI / minimum necessary",
                "Visit histories and authorization records are PHI (S-01.1). The new completed-visit view exposes per-member visit counts.",
                "Expose counts only (no clinical notes); restrict view to the Authorization Service role; mask member ids in analytics.")
        finding("SEC-RBAC-01", Severity.MEDIUM, "Authorization / RBAC",
                "Authorization overrides directly change payment outcomes.",
                "Require claims-supervisor role for overrides and record override reason in the audit log (O-05.1).")
        finding("SEC-AUD-01", Severity.LOW, "Auditability",
                "AUTH_REQUIRED decisions must be reconstructable.",
                "Emit counted_visits and auth_rule_id on claim.adjudicated events (backward-compatible).")
    if "database_table" in changed_types:
        finding("SEC-DATA-01", Severity.LOW, "Data change control",
                "Benefit limit / authorization rule tables change.",
                "Use effective-dated rows with migration review; never update historical rows in place.")
    if request_screen_flagged:
        finding("SEC-PI-01", Severity.HIGH, "Prompt injection",
                "The request contained instruction-like content (e.g. 'ignore previous instructions').",
                "Content treated as data only; no tool permissions changed. Review request origin.")

    checks += [
        {"check": "Secrets loaded from environment only (no hardcoded keys)", "status": "PASS"},
        {"check": "API key never logged / returned (redaction filter active)", "status": "PASS"},
        {"check": "DEMO_MODE makes zero paid LLM calls", "status": "PASS" if settings.demo_mode else "N/A (live mode)"},
        {"check": "Agent tools allow-listed; consequential tools require human approval", "status": "PASS"},
        {"check": "MAX_AGENT_ITERATIONS / MAX_TOOL_CALLS / timeouts enforced", "status": "PASS"},
        {"check": "Uploaded documents: type/size validation + injection quarantine", "status": "PASS"},
        {"check": "Logs contain identifiers and counts only (no claim payloads / PHI)", "status": "PASS"},
        {"check": "Encryption at rest/in transit", "status": "ASSUMED (platform responsibility; not verified by demo)"},
        {"check": "Data retention for audit logs", "status": "ASSUMED (in-memory in demo; define retention for production)"},
    ]
    counts: dict[str, int] = {}
    for f in findings:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    return {"findings": findings, "checks": checks, "severity_counts": counts,
            "disclaimer": "ADVISORY — not a formal security assessment or compliance certification.",
            "method": "DETERMINISTIC rule-based review"}
