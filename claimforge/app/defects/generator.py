"""Jira-style defect & SDLC feedback generation (DETERMINISTIC TEMPLATE, MOCKED tracker).

Defects are created in an in-memory store only. No external tracker (Jira, Azure DevOps,
ServiceNow) is connected — see app/integrations/adapters.py for the adapter interfaces.
"""

from __future__ import annotations

from app.models.domain import Defect, Remediation, RootCause, Severity


def generate_defect(rc: RootCause, rem: Remediation, sequence: int = 1042, incident_id: str = "INC-SYN-2407") -> Defect:
    sample = rc.sample_claims[0] if rc.sample_claims else {}
    completed = sample.get("prior_completed_visits", 8)
    cancelled = sample.get("prior_cancelled_visits", 3)
    return Defect(
        key=f"CLAIMS-{sequence}",
        title="Incorrect authorization threshold calculation for physiotherapy",
        severity=Severity.HIGH,
        priority="P1",
        description=("Cancelled visits are counted toward the physiotherapy prior-authorization threshold "
                     f"({rc.changed_rule}). Members with fewer than 10 COMPLETED visits are denied AUTH_REQUIRED. "
                     f"ClaimIQ: {rc.anomaly_summary}"),
        expected="Only COMPLETED visits count toward the 10-visit authorization threshold (policy P-01.3, P-14.3).",
        actual="COMPLETED + CANCELLED visits are counted.",
        reproduction=[
            "Environment: ClaimForge simulation (SYNTHETIC DATA).",
            f"Synthetic member {sample.get('member_id', 'MBR-SYN-XXXXXX')} with {completed} COMPLETED and "
            f"{cancelled} CANCELLED physiotherapy visits in benefit year 2026; no authorization on file.",
            f"Submit physiotherapy claim (visit {completed + 1}) after release 2.4 deployment.",
            "Observe: DENIED / AUTH_REQUIRED. Expected: APPROVED (authorization not yet required).",
            f"Regression test: {rem.regression_test.test_id}.",
        ],
        source_requirement=rc.source_requirement or "BR-391",
        introduced_in_release=f"Release {rc.correlated_release or '2.4'}",
        rule_id=rc.changed_rule or "AUTH_RULE_184",
        policy_section=rc.policy_section,
        linked_incident=incident_id,
        regression_test_id=rem.regression_test.test_id,
        affected_claims=rc.affected_claims,
        labels=["claimiq", "physiotherapy", "authorization", "synthetic-demo", f"confidence-{rc.confidence.lower()}"],
    )


def sdlc_feedback(rc: RootCause, rem: Remediation, defect: Defect) -> dict:
    return {
        "backlog_items": [
            {"type": "Bug", "key": defect.key, "title": defect.title, "priority": defect.priority},
            {"type": "Requirement revision", "key": f"{defect.source_requirement}-R1",
             "title": "Promote AC-7 (cancelled visits excluded) to a mandatory release gate for AUTH_RULE_184"},
            {"type": "Test", "key": rem.regression_test.test_id, "title": rem.regression_test.title},
            {"type": "Monitoring", "key": "MON-ALERT-184",
             "title": "Alert: AUTH_REQUIRED denials with < threshold COMPLETED visits must be zero"},
            {"type": "Test data", "key": "QA-DATA-17",
             "title": "Synthetic generators must include CANCELLED / NO_SHOW visit histories"},
            {"type": "Operations", "key": "OPS-REPROC-2407",
             "title": f"Reprocess {rem.claims_to_reprocess} wrongly denied synthetic claims after hotfix (approval O-05.2)"},
        ],
        "lessons": [
            "The specification (BR-391 AC-7) was correct; the defect was an implementation drift in visit counting.",
            "Release-aware monitoring (compare to approved simulation) separated the defect from the intended auth effect.",
            "Production evidence produced an executable regression test that fails on the defective build.",
        ],
        "status": "FEEDBACK RECORDED (in-memory; MOCKED backlog — no external tracker connected)",
    }
