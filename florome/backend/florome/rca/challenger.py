"""RCA Evidence Challenger.

Generalises Project A's analytical Evidence Challenger (agents/evidence_challenger.py) from conversation analytics
to operational RCA. It argues against the engine's conclusion and may only *downgrade* it, never upgrade:

  correlation_only        the root link rests on timing/topology without a direct error signature
  competing_explanations  another root-cause hypothesis has the same status
  causal_chain_gaps       a link between root and symptom is unverified
  evidence_gaps           in-scope resources with no logs/traces collected, or evidence kinds never collected
  single_source           all evidence comes from one system
  unexplained_anomalies   anomalous in-scope resources that are not on the causal chain
"""

from __future__ import annotations

from typing import Any

from florome.rca.engine import EvidenceItem, Topology

DOWNGRADE = {"confirmed": "probable", "probable": "inconclusive", "inconclusive": "inconclusive"}


def _c(name: str, status: str, detail: str) -> dict[str, Any]:
    return {"check": name, "status": status, "detail": detail}


def challenge(report: dict[str, Any], topo: Topology, evidence: list[EvidenceItem]) -> dict[str, Any]:
    concl = report["conclusion"]
    hyps = {h["id"]: h for h in report["hypotheses"]}
    checks: list[dict[str, Any]] = []
    root = hyps.get(concl.get("root_hypothesis_id") or "")
    downgrade_reasons: list[str] = []

    if root:
        sig = next((t["result"] for t in root["tests"] if t["test"] in ("signature_match", "capacity_breach_near_onset")), "unknown")
        if sig != "pass":
            checks.append(_c("correlation_only", "fail", "The root link is temporal/topological only; correlation is not established causation."))
            if concl["status"] == "confirmed":
                downgrade_reasons.append("correlation_only")
        else:
            checks.append(_c("correlation_only", "pass", "The root hypothesis is linked by a direct error signature, not timing alone."))
    checks.append(_c("competing_explanations", "fail" if concl.get("competing_hypotheses") else "pass",
                     f"Equally supported alternatives: {', '.join(concl['competing_hypotheses'])}" if concl.get("competing_hypotheses")
                     else "No alternative root-cause hypothesis has equal support."))

    weak = [c for c in concl.get("causal_chain", []) if c["link_status"] in ("probable", "inconclusive", "unlinked")]
    if weak:
        checks.append(_c("causal_chain_gaps", "warn", "Links without a direct signature: " +
                         ", ".join(f"{topo.name(c['resource_id'])} ({c['link_status']})" for c in weak)))
        if any(c["link_status"] == "unlinked" for c in weak) and concl["status"] == "confirmed":
            downgrade_reasons.append("causal_chain_gaps")
    else:
        checks.append(_c("causal_chain_gaps", "pass", "Every link from root to symptom is supported by a direct signature."))

    have = {(e.resource_id, e.kind) for e in evidence}
    kinds = {e.kind for e in evidence}
    no_text = [topo.name(r) for r in report["scope"] if not any((r, k) in have for k in ("log", "trace", "status"))
               and topo.resources.get(r, {}).get("kind") not in ("ci_pipeline",)]
    missing_kinds = sorted({"log", "metric", "deployment", "trace"} - kinds)
    detail = []
    if no_text:
        detail.append("no logs/traces for " + ", ".join(no_text))
    if missing_kinds:
        detail.append("evidence kinds never collected: " + ", ".join(missing_kinds))
    checks.append(_c("evidence_gaps", "warn" if detail else "pass", "; ".join(detail) or "Logs or traces exist for every in-scope resource."))

    sources = {e.source_system for e in evidence}
    checks.append(_c("single_source", "warn" if len(sources) <= 1 else "pass",
                     f"Evidence sources: {', '.join(sorted(sources)) or 'none'}."
                     + (" Independent corroboration from a second system is unavailable." if len(sources) <= 1 else "")))

    on_chain = {c["resource_id"] for c in concl.get("causal_chain", [])}
    unexplained = [topo.name(r) for r in report["anomaly_onset"] if r in report["scope"] and r not in on_chain]
    checks.append(_c("unexplained_anomalies", "warn" if unexplained else "pass",
                     ("Anomalous but not on the causal chain: " + ", ".join(unexplained)) if unexplained
                     else "Every anomalous in-scope resource lies on the causal chain."))

    original = concl["status"]
    final = original
    for _ in downgrade_reasons:
        final = DOWNGRADE[final]
    return {"checks": checks, "original_status": original, "final_status": final, "downgraded_by": downgrade_reasons}
