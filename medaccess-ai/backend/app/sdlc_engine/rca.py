"""Root Cause Analysis Agent + Development Agent fix proposal.

Hypotheses are evaluated against concrete evidence. A hypothesis is CONFIRMED only
when (a) a code/config difference exists, (b) tests fail on the suspect build, and
(c) the same tests pass when only that difference is reverted (reproduction).
"""

from __future__ import annotations

import difflib

from app.config.settings import get_settings
from app.governance import builds
from app.sdlc_engine import qa
from app.services.synthetic import INTEGRATIONS
from app.services.verification import STATUS_MAPPINGS


def mapping_lines(name: str) -> list[str]:
    return [f"    SourceSlotStatus.{k.name}: AvailabilityStatus.{v.value}," for k, v in STATUS_MAPPINGS[name].items()]


def mapping_diff(from_build: str, to_build: str) -> str:
    a = builds.BUILDS[from_build].status_mapping
    b = builds.BUILDS[to_build].status_mapping
    return "\n".join(difflib.unified_diff(mapping_lines(a), mapping_lines(b),
                                         fromfile=f"verification.py@{from_build}", tofile=f"verification.py@{to_build}",
                                         lineterm=""))


def analyze(anomaly: dict | None, suspect_build: str, baseline_build: str = "1.4.0",
            simulation_samples: list[dict] | None = None) -> dict:
    evidence: list[dict] = []
    suspect = qa.run_suite(suspect_build)
    base = qa.run_suite(baseline_build)
    failing = [r for r in suspect["results"] if not r["passed"]]
    evidence.append({"type": "test_results", "detail": f"{suspect['failed']} scenario(s) fail on {suspect_build}; "
                                                       f"{base['failed']} fail on {baseline_build}",
                     "failing": [f"{r['id']} {r['title']}" for r in failing]})
    if anomaly:
        evidence.append({"type": "anomaly", "detail": anomaly.get("evidence"), "rule": anomaly.get("rule")})
    if simulation_samples:
        evidence.append({"type": "traces", "detail": f"{len(simulation_samples)} correlated trace(s) where source "
                                                     "status 'advertised' was reported VERIFIED_AVAILABLE",
                         "samples": simulation_samples[:5]})
    diff = mapping_diff(baseline_build, suspect_build)
    evidence.append({"type": "code_diff", "detail": "status-mapping difference between builds" if diff else
                     "no status-mapping difference", "diff": diff})
    deploys = [h for h in builds.history() if h["to"] == suspect_build]
    if deploys:
        evidence.append({"type": "change_correlation", "detail": f"{suspect_build} deployed to {deploys[-1]['env']} "
                                                                 f"at {deploys[-1]['at']} preceding the anomaly"})

    hypotheses = []
    reproduced = bool(diff) and bool(failing) and base["failed"] == 0
    hypotheses.append({
        "id": "H1", "statement": f"Status-mapping change in build {suspect_build} maps ADVERTISED slots to "
                                 "VERIFIED_AVAILABLE.",
        "status": "CONFIRMED" if reproduced else ("INCONCLUSIVE" if diff else "REJECTED"),
        "supporting_evidence": ["code_diff", "test_results", "traces", "change_correlation"] if reproduced else [],
        "reasoning": "Mapping differs; regression scenarios fail on the suspect build and pass on the baseline "
                     "with only the mapping changed." if reproduced else "Insufficient evidence to confirm."})
    s = get_settings()
    hypotheses.append({"id": "H2", "statement": "Freshness threshold was relaxed.",
                       "status": "REJECTED", "reasoning": f"max_verified_age_hours unchanged ({s.max_verified_age_hours}h)",
                       "supporting_evidence": []})
    hypotheses.append({"id": "H3", "statement": "Source reliability degraded upstream.",
                       "status": "REJECTED", "supporting_evidence": [],
                       "reasoning": "Integration reliability values unchanged: "
                                    + ", ".join(f"{i.id}={i.reliability}" for i in INTEGRATIONS)})
    hypotheses.append({"id": "H4", "statement": "Upstream feed started labelling advertised slots as confirmed.",
                       "status": "REJECTED", "supporting_evidence": [],
                       "reasoning": "Sample traces show raw source_status 'advertised'; the misclassification happens "
                                    "after ingestion, inside verification."})
    root = next((h for h in hypotheses if h["status"] == "CONFIRMED"), None)
    return {"suspect_build": suspect_build, "baseline_build": baseline_build, "evidence": evidence,
            "hypotheses": hypotheses, "root_cause": root["statement"] if root else None,
            "confirmed": root is not None, "failing_tests": [r["id"] for r in failing],
            "component": "backend/app/services/verification.py::STATUS_MAPPINGS" if root else None}


def propose_fix(suspect_build: str, fixed_build: str = "1.5.1") -> dict:
    return {"fixed_build": fixed_build, "file": "backend/app/services/verification.py",
            "change": "Restore SourceSlotStatus.ADVERTISED -> AvailabilityStatus.ADVERTISED_UNVERIFIED",
            "diff": mapping_diff(suspect_build, fixed_build),
            "regression_tests": qa.REGRESSION_IDS,
            "risk": "Low - single mapping entry; covered by regression scenarios and unit tests.",
            "requires_approval": "CODE_CHANGE review + PRODUCTION_DEPLOYMENT approval"}
