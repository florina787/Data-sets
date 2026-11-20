"""Deterministic root-cause analysis engine.

Input: an incident (symptomatic resource + detection time), the dependency topology, and the evidence collected
from connectors. Output: a report with competing hypotheses, each classified as

  confirmed     every required test passes, including a direct error-signature link
  probable      required tests pass but the link rests on timing/topology (no direct signature)
  inconclusive  evidence is missing to run a required test, or explanations compete
  disproven     a required test fails against observed evidence

Every test names the evidence ids it used. No confidence percentages are produced: the basis of a status is the
list of tests and their outcomes. No language model is involved in any classification.

Hypothesis generators
---------------------
change       a deployment or configuration change on the symptomatic resource or any upstream resource
saturation   a capacity metric (CPU, memory) on an in-scope resource
propagation  a failure travelling along a dependency edge between two anomalous resources
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

ENGINE_VERSION = "1.0.0"
CHANGE_PROXIMITY = timedelta(minutes=120)
SATURATION_WINDOW = timedelta(minutes=30)
STATUS_RANK = {"confirmed": 3, "probable": 2, "inconclusive": 1, "disproven": 0}


@dataclass
class EvidenceItem:
    id: str
    resource_id: str
    kind: str
    observed_at: datetime
    summary: str
    payload: dict[str, Any]
    source_system: str = ""


@dataclass
class Topology:
    resources: dict[str, dict[str, Any]]  # id -> {name, kind, platform, ...}
    edges: list[tuple[str, str, str]]  # (source, target, kind)

    def parents(self, rid: str) -> list[str]:
        return [s for s, t, _ in self.edges if t == rid]

    def children(self, rid: str) -> list[str]:
        return [t for s, t, _ in self.edges if s == rid]

    def _walk(self, start: str, step) -> list[str]:  # noqa: ANN001
        seen: list[str] = []
        q = deque(step(start))
        while q:
            n = q.popleft()
            if n not in seen and n != start:
                seen.append(n)
                q.extend(step(n))
        return seen

    def ancestors(self, rid: str) -> list[str]:
        return self._walk(rid, self.parents)

    def descendants(self, rid: str) -> list[str]:
        return self._walk(rid, self.children)

    def name(self, rid: str) -> str:
        return self.resources.get(rid, {}).get("name", rid)


@dataclass
class Hypothesis:
    id: str
    kind: str
    role: str  # root_cause | propagation
    title: str
    candidate_resource_id: str
    tests: list[dict[str, Any]] = field(default_factory=list)
    status: str = "inconclusive"
    basis: str = ""
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    related_resource_id: str | None = None  # propagation: the downstream resource

    def as_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "role": self.role, "title": self.title, "candidate_resource_id": self.candidate_resource_id,
                "related_resource_id": self.related_resource_id, "status": self.status, "basis": self.basis, "tests": self.tests,
                "supporting_evidence": sorted(set(self.supporting)), "contradicting_evidence": sorted(set(self.contradicting))}


# ---------------------------------------------------------------------------------------------------- anomalies

def is_anomalous(ev: EvidenceItem) -> bool:
    p = ev.payload
    if ev.kind in ("log", "status"):
        return str(p.get("level", "")).upper() in ("ERROR", "CRITICAL", "FATAL")
    if ev.kind == "metric" and "threshold" in p:
        return metric_breached(p)
    if ev.kind == "trace":
        return int(p.get("status", 0)) >= 500
    return False


def metric_breached(p: dict[str, Any]) -> bool:
    return p["value"] > p["threshold"] if p.get("direction", "above") == "above" else p["value"] < p["threshold"]


def error_text(ev: EvidenceItem) -> str:
    return f"{ev.summary} {ev.payload.get('message', '')}".lower()


def _t(name: str, result: str, detail: str, evidence: list[str] | None = None) -> dict[str, Any]:
    return {"test": name, "result": result, "detail": detail, "evidence": evidence or []}


def _results(h: Hypothesis) -> dict[str, str]:
    return {t["test"]: t["result"] for t in h.tests}


# --------------------------------------------------------------------------------------------------- the engine

def analyse(incident: dict[str, Any], topo: Topology, evidence: list[EvidenceItem]) -> dict[str, Any]:
    primary = incident["primary_resource_id"]
    scope = [primary, *topo.ancestors(primary)]
    by_res: dict[str, list[EvidenceItem]] = {r: [] for r in topo.resources}
    for ev in sorted(evidence, key=lambda e: e.observed_at):
        by_res.setdefault(ev.resource_id, []).append(ev)

    anomalies = {r: [e for e in by_res.get(r, []) if is_anomalous(e) and not e.payload.get("capacity")] for r in topo.resources}
    onset: dict[str, datetime] = {r: a[0].observed_at for r, a in anomalies.items() if a}
    errors = {r: [e for e in by_res.get(r, []) if e.kind in ("log", "status", "trace") and is_anomalous(e)] for r in topo.resources}

    def earlier_anomalous_ancestors(r: str) -> list[str]:
        if r not in onset:
            return [a for a in topo.ancestors(r) if a in onset]
        return [a for a in topo.ancestors(r) if a in onset and onset[a] < onset[r]]

    hyps: list[Hypothesis] = []

    # change hypotheses ------------------------------------------------------------------------------------
    for r in scope:
        for ch in [e for e in by_res.get(r, []) if e.kind in ("deployment", "config_change")]:
            name = topo.name(r)
            h = Hypothesis(f"H{len(hyps) + 1}", "change", "root_cause", f"{ch.kind.replace('_', ' ').title()} on {name}: {ch.summary}", r)
            h.supporting.append(ch.id)
            if r in onset:
                ok = ch.observed_at <= onset[r]
                h.tests.append(_t("temporal_precedence", "pass" if ok else "fail",
                                  f"Change at {ch.observed_at:%H:%M}, first anomaly on {name} at {onset[r]:%H:%M}.", [ch.id, anomalies[r][0].id]))
                (h.supporting if ok else h.contradicting).append(anomalies[r][0].id)
                gap = onset[r] - ch.observed_at
                h.tests.append(_t("proximity", "pass" if timedelta(0) <= gap <= CHANGE_PROXIMITY else "fail",
                                  f"Anomaly began {int(gap.total_seconds() // 60)} min after the change (window {int(CHANGE_PROXIMITY.total_seconds() // 60)} min)."))
            else:
                h.tests.append(_t("temporal_precedence", "fail", f"No anomaly was observed on {name} after the change.", [ch.id]))
            terms = [str(t).lower() for t in ch.payload.get("signature_terms", []) if t]
            errs = [e for e in errors.get(r, []) if e.observed_at >= ch.observed_at]
            if not errs:
                h.tests.append(_t("signature_match", "unknown", f"No error logs/traces on {name} after the change to compare."))
            else:
                hits = [e for e in errs if any(t in error_text(e) for t in terms)]
                if hits:
                    h.tests.append(_t("signature_match", "pass", f"{len(hits)} of {len(errs)} errors reference the change ({', '.join(terms)}).",
                                      [e.id for e in hits]))
                    h.supporting += [e.id for e in hits]
                else:
                    h.tests.append(_t("signature_match", "fail", f"None of {len(errs)} errors reference the change ({', '.join(terms) or 'no terms'}).",
                                      [e.id for e in errs]))
                    h.contradicting += [e.id for e in errs]
            earlier = earlier_anomalous_ancestors(r)
            h.tests.append(_t("no_earlier_upstream_anomaly", "fail" if earlier else "pass",
                              ("Upstream resources were already anomalous: " + ", ".join(topo.name(a) for a in earlier)) if earlier
                              else f"No upstream resource of {name} was anomalous earlier.",
                              [anomalies[a][0].id for a in earlier]))
            h.contradicting += [anomalies[a][0].id for a in earlier]
            h.tests.append(_t("dependency_path", "pass", f"{name} is {'the symptomatic resource' if r == primary else 'upstream of ' + topo.name(primary)}."))
            hyps.append(h)

    # saturation hypotheses --------------------------------------------------------------------------------
    for r in scope:
        cap = [e for e in by_res.get(r, []) if e.kind == "metric" and e.payload.get("capacity")]
        if not cap:
            continue
        name = topo.name(r)
        h = Hypothesis(f"H{len(hyps) + 1}", "saturation", "root_cause", f"Resource saturation on {name} ({cap[0].payload.get('name')})", r)
        ref = onset.get(r)
        window = [e for e in cap if ref is None or ref - SATURATION_WINDOW <= e.observed_at <= ref + timedelta(minutes=5)]
        if not window:
            h.tests.append(_t("capacity_breach_near_onset", "unknown", "No capacity samples near the anomaly onset."))
        else:
            breached = [e for e in window if metric_breached(e.payload)]
            if breached:
                h.tests.append(_t("capacity_breach_near_onset", "pass", "Capacity threshold exceeded near onset.", [e.id for e in breached]))
                h.supporting += [e.id for e in breached]
            else:
                h.tests.append(_t("capacity_breach_near_onset", "fail",
                                  "; ".join(f"{e.payload['name']} {e.payload['value']}{e.payload.get('unit', '')} below threshold {e.payload['threshold']}" for e in window),
                                  [e.id for e in window]))
                h.contradicting += [e.id for e in window]
        h.tests.append(_t("dependency_path", "pass", f"{name} is in the investigation scope."))
        hyps.append(h)

    # propagation hypotheses -------------------------------------------------------------------------------
    for s, t, kind in topo.edges:
        if s not in scope or t not in scope or s not in onset or t not in onset:
            continue
        h = Hypothesis(f"H{len(hyps) + 1}", "propagation", "propagation", f"Failure propagated from {topo.name(s)} to {topo.name(t)} ({kind})", s,
                       related_resource_id=t)
        ok = onset[s] <= onset[t]
        h.tests.append(_t("temporal_precedence", "pass" if ok else "fail",
                          f"{topo.name(s)} anomalous at {onset[s]:%H:%M}, {topo.name(t)} at {onset[t]:%H:%M}.",
                          [anomalies[s][0].id, anomalies[t][0].id]))
        (h.supporting if ok else h.contradicting).extend([anomalies[s][0].id, anomalies[t][0].id])
        h.tests.append(_t("dependency_path", "pass", f"Declared {kind} edge {topo.name(s)} -> {topo.name(t)}."))
        downstream_errs = errors.get(t, [])
        if not downstream_errs:
            h.tests.append(_t("signature_match", "unknown", f"No error messages on {topo.name(t)} to link to {topo.name(s)}."))
        else:
            needle = topo.name(s).lower()
            hits = [e for e in downstream_errs if needle in error_text(e)]
            h.tests.append(_t("signature_match", "pass" if hits else "fail",
                              f"{len(hits)} error(s) on {topo.name(t)} name {topo.name(s)}." if hits else f"Errors on {topo.name(t)} do not mention {topo.name(s)}.",
                              [e.id for e in (hits or downstream_errs)]))
            h.supporting += [e.id for e in hits]
        hyps.append(h)

    for h in hyps:
        classify(h)

    conclusion = conclude(hyps, topo, primary, onset)
    return {
        "engine_version": ENGINE_VERSION,
        "scope": scope,
        "anomaly_onset": {r: t.isoformat() for r, t in sorted(onset.items(), key=lambda kv: kv[1])},
        "hypotheses": [h.as_dict() for h in hyps],
        "conclusion": conclusion,
        "timeline": [{"evidence_id": e.id, "resource_id": e.resource_id, "resource": topo.name(e.resource_id), "kind": e.kind,
                      "at": e.observed_at.isoformat(), "summary": e.summary, "anomalous": is_anomalous(e)}
                     for e in sorted(evidence, key=lambda e: e.observed_at)],
    }


def classify(h: Hypothesis) -> None:
    r = _results(h)
    passed = [k for k, v in r.items() if v == "pass"]
    failed = [k for k, v in r.items() if v == "fail"]
    unknown = [k for k, v in r.items() if v == "unknown"]
    if h.kind == "change":
        if r.get("temporal_precedence") == "fail" or r.get("dependency_path") == "fail":
            h.status = "disproven"
        elif r.get("signature_match") == "fail" and r.get("no_earlier_upstream_anomaly") == "fail":
            h.status = "disproven"
        elif all(r.get(k) == "pass" for k in ("temporal_precedence", "signature_match", "no_earlier_upstream_anomaly", "dependency_path")):
            h.status = "confirmed"
        elif r.get("no_earlier_upstream_anomaly") == "pass" and r.get("signature_match") == "unknown" and r.get("proximity") == "pass":
            h.status = "probable"
        else:
            h.status = "inconclusive"
    elif h.kind == "saturation":
        res = r.get("capacity_breach_near_onset")
        h.status = {"fail": "disproven", "pass": "probable", "unknown": "inconclusive"}[res]  # saturation alone is never 'confirmed'
    else:  # propagation
        if r.get("temporal_precedence") == "fail" or r.get("signature_match") == "fail":
            h.status = "disproven" if r.get("temporal_precedence") == "fail" else "inconclusive"
        elif r.get("signature_match") == "pass":
            h.status = "confirmed"
        else:
            h.status = "probable"
    h.basis = (f"Passed: {', '.join(passed) or 'none'}. Failed: {', '.join(failed) or 'none'}. "
               f"Not testable with available evidence: {', '.join(unknown) or 'none'}.")


def conclude(hyps: list[Hypothesis], topo: Topology, primary: str, onset: dict[str, datetime]) -> dict[str, Any]:
    roots = [h for h in hyps if h.role == "root_cause" and h.status != "disproven"]
    if not roots:
        return {"status": "inconclusive", "root_hypothesis_id": None, "root_resource_id": None, "causal_chain": [],
                "competing_hypotheses": [], "statement": "No tested hypothesis explains the incident. Further diagnostics are required.",
                "next_diagnostics": ["Collect traces and logs for upstream resources", "Check for changes not captured by connected systems"]}
    best_rank = max(STATUS_RANK[h.status] for h in roots)
    top = [h for h in roots if STATUS_RANK[h.status] == best_rank]
    # Prefer the candidate whose resource became anomalous first (furthest upstream in time); stable on id.
    top.sort(key=lambda h: (h.candidate_resource_id not in onset,
                            onset[h.candidate_resource_id].timestamp() if h.candidate_resource_id in onset else 0.0, h.id))
    root = top[0]
    competing = [h.id for h in top[1:]]
    status = root.status
    statement = f"{root.title}."
    if competing:
        status = "inconclusive"
        statement = f"Competing explanations remain equally supported: {', '.join([root.id, *competing])}."
    chain = _chain(hyps, topo, root.candidate_resource_id, primary)
    return {"status": status, "root_hypothesis_id": root.id, "root_resource_id": root.candidate_resource_id,
            "causal_chain": chain, "competing_hypotheses": competing, "statement": statement,
            "next_diagnostics": [] if status == "confirmed" else
            ["Collect error logs on the candidate resource after the change", "Compare against a period without the change"]}


def _chain(hyps: list[Hypothesis], topo: Topology, root: str, primary: str) -> list[dict[str, Any]]:
    """Follow non-disproven propagation hypotheses from the root resource down to the symptom."""
    links = {(h.candidate_resource_id, h.related_resource_id): h for h in hyps if h.role == "propagation" and h.status != "disproven"}
    path, node, seen = [{"resource_id": root, "link_status": "root", "hypothesis_id": None}], root, {root}
    while node != primary:
        nxt = [(t, links[(node, t)]) for t in topo.children(node) if (node, t) in links and t not in seen]
        if not nxt:
            path.append({"resource_id": primary, "link_status": "unlinked", "hypothesis_id": None})
            break
        node, h = nxt[0]
        seen.add(node)
        path.append({"resource_id": node, "link_status": h.status, "hypothesis_id": h.id})
    return path
