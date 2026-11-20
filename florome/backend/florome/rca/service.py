"""RCA Investigation Agent: collects evidence through connectors, runs the engine and the challenger, persists."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.actions.planner import build_plan
from florome.connectors.base import Capability, ConnectorError
from florome.context import AppContext
from florome.models import Connection, Dependency, Evidence, Hypothesis, Incident, RCAReport, Resource, as_utc, utcnow
from florome.rca.challenger import challenge
from florome.rca.engine import ENGINE_VERSION, EvidenceItem, Topology, analyse
from florome.security import audit
from florome.security.injection import sanitize, scan
from florome.security.rbac import Principal
from florome.security.redaction import redact

LOOKBACK = timedelta(hours=6)
KIND_CAPS = {"log": Capability.FETCH_LOGS, "metric": Capability.FETCH_METRICS, "trace": Capability.FETCH_TRACES,
             "deployment": Capability.FETCH_DEPLOYMENTS, "config_change": Capability.FETCH_CHANGES, "status": Capability.READ_STATUS}
PREVENTIVE = {
    "change": ["Gate deployments on automated contract tests for payload/schema changes.",
               "Use canary or staged rollout with automatic halt on error-rate increase.",
               "Add a data-quality gate at ingestion so incomplete batches are quarantined, not propagated."],
    "saturation": ["Review capacity limits and autoscaling bounds for the resource.", "Alert on sustained utilisation before saturation."],
}


def load_topology(db: Session, tenant_id: str) -> Topology:
    res = db.scalars(select(Resource).where(Resource.tenant_id == tenant_id)).all()
    deps = db.scalars(select(Dependency).where(Dependency.tenant_id == tenant_id)).all()
    return Topology({r.id: {"name": r.name, "kind": r.kind, "platform": r.platform, "environment": r.environment,
                            "connection_id": r.connection_id, "source_ref": r.source_ref} for r in res},
                    [(d.source_id, d.target_id, d.kind) for d in deps])


def evidence_hash(ev: Evidence) -> str:
    return audit.sha256({"kind": ev.kind, "resource": ev.resource_id, "at": as_utc(ev.observed_at).isoformat(), "summary": ev.summary,
                         "payload": ev.payload, "source_system": ev.source_system, "source_ref": ev.source_ref})


async def collect_evidence(db: Session, ctx: AppContext, incident: Incident, topo: Topology) -> dict[str, Any]:
    scope = [incident.primary_resource_id, *topo.ancestors(incident.primary_resource_id)]
    start, end = as_utc(incident.detected_at) - LOOKBACK, utcnow() + timedelta(minutes=1)
    existing = {(e.resource_id, e.source_ref) for e in db.scalars(select(Evidence).where(Evidence.incident_id == incident.id))}
    report: dict[str, Any] = {"collected": 0, "skipped_existing": 0, "errors": [], "unsupported": []}
    for rid in scope:
        r = topo.resources[rid]
        if not r.get("connection_id") or not ctx.registry.has(r["connection_id"]):
            report["errors"].append(f"{r['name']}: no connector instance")
            continue
        conn_row = db.get(Connection, r["connection_id"])
        if conn_row is None or conn_row.status != "verified":
            report["errors"].append(f"{r['name']}: connection not verified")
            continue
        connector = ctx.registry.get(r["connection_id"])
        caps = connector.capabilities()
        kinds = {k for k, c in KIND_CAPS.items() if c in caps}
        report["unsupported"] += [f"{r['name']}: {k}" for k in KIND_CAPS if k not in kinds]
        try:
            observations = await connector.fetch_observations(r["source_ref"], start, end, kinds)
        except ConnectorError as exc:
            report["errors"].append(f"{r['name']}: {exc}")
            continue
        for o in observations:
            if (rid, o.source_ref) in existing:
                report["skipped_existing"] += 1
                continue
            payload = redact(o.payload)
            flags = scan(o.summary) + scan(str(o.payload.get("message", "")))
            if flags:
                payload["_untrusted_content_flags"] = flags
            ev = Evidence(tenant_id=incident.tenant_id, incident_id=incident.id, resource_id=rid, kind=o.kind, observed_at=o.observed_at,
                          summary=redact(sanitize(o.summary, 1000)), payload=payload, source_system=connector.connector_type,
                          source_ref=o.source_ref, collected_by=r["connection_id"], is_demo=connector.is_simulated, content_hash="")
            ev.content_hash = evidence_hash(ev)
            db.add(ev)
            report["collected"] += 1
    db.flush()
    return report


async def run_rca(db: Session, ctx: AppContext, actor: Principal, incident: Incident) -> RCAReport:
    topo = load_topology(db, incident.tenant_id)
    collection = await collect_evidence(db, ctx, incident, topo)
    rows = db.scalars(select(Evidence).where(Evidence.incident_id == incident.id)).all()
    items = [EvidenceItem(e.id, e.resource_id, e.kind, as_utc(e.observed_at), e.summary, e.payload, e.source_system) for e in rows]
    inc = {"id": incident.id, "title": incident.title, "primary_resource_id": incident.primary_resource_id,
           "detected_at": as_utc(incident.detected_at).isoformat(), "severity": incident.severity, "symptoms": incident.symptoms}
    report = analyse(inc, topo, items)
    report["incident"] = inc
    report["challenge"] = challenge(report, topo, items)
    final = report["challenge"]["final_status"]
    report["conclusion"]["final_status"] = final
    report["evidence_collection"] = collection

    root_id = report["conclusion"].get("root_resource_id")
    chain_ids = [c["resource_id"] for c in report["conclusion"]["causal_chain"]]
    impacted = list(dict.fromkeys([*chain_ids, incident.primary_resource_id, *topo.descendants(incident.primary_resource_id)]))
    report["affected_systems"] = [{"resource_id": r, "name": topo.name(r), "platform": topo.resources[r]["platform"],
                                   "kind": topo.resources[r]["kind"], "role": "root" if r == root_id else "impacted"} for r in impacted]
    report["business_impact"] = [a for a in report["affected_systems"] if a["kind"] == "business_process"]
    report["evidence_graph"] = _evidence_graph(report, topo, items)
    ev_by_id = {e.id: {"kind": e.kind, "payload": e.payload} for e in rows}
    outline = build_plan(report, topo, ev_by_id, lambda cid: ctx.registry.get(cid) if ctx.registry.has(cid) else None, utcnow())
    report["recommended_remediation"] = [{"action": s["title"], "target": s["target_name"], "params": s["params"], "risk": s["risk"]}
                                         for s in outline["steps"]]
    report["remediation_notes"] = outline["notes"]
    report["risks"] = [f"{s['title']} on {s['target_name']}: {s['risk']} risk; rollback: {s['rollback']}" for s in outline["steps"]]
    report["validation_procedure"] = [f"Verify {topo.name(r)} returns to healthy state and its key metric is within threshold"
                                      for r in outline["validation_targets"]]
    root_h = next((h for h in report["hypotheses"] if h["id"] == report["conclusion"].get("root_hypothesis_id")), None)
    report["preventive_measures"] = PREVENTIVE.get(root_h["kind"], []) if root_h and final in ("confirmed", "probable") else []
    report["data_mode"] = "demo" if any(e.is_demo for e in rows) else "live"

    rca = RCAReport(tenant_id=incident.tenant_id, incident_id=incident.id, engine_version=ENGINE_VERSION, conclusion_status=final,
                    report=report, report_hash=audit.sha256(report))
    db.add(rca)
    db.flush()
    for h in report["hypotheses"]:
        db.add(Hypothesis(id=f"{rca.id}-{h['id']}", tenant_id=incident.tenant_id, rca_id=rca.id, incident_id=incident.id, kind=h["kind"],
                          role=h["role"], title=h["title"], candidate_resource_id=h["candidate_resource_id"], status=h["status"],
                          basis=h["basis"], tests=h["tests"], supporting_evidence=h["supporting_evidence"],
                          contradicting_evidence=h["contradicting_evidence"]))
    incident.status = "investigating" if incident.status == "open" else incident.status
    incident.fingerprint = fingerprint(report, topo)
    audit.record(db, incident.tenant_id, actor.user_id, "rca.run", incident.id, "success",
                 {"rca_id": rca.id, "status": final, "report_hash": rca.report_hash, "evidence": len(items)})
    return rca


def _evidence_graph(report: dict[str, Any], topo: Topology, items: list[EvidenceItem]) -> dict[str, Any]:
    nodes, edges = [], []
    used = set()
    for h in report["hypotheses"]:
        used |= set(h["supporting_evidence"]) | set(h["contradicting_evidence"])
    for r in report["scope"]:
        nodes.append({"id": r, "type": "resource", "label": topo.name(r), "platform": topo.resources[r]["platform"],
                      "anomalous": r in report["anomaly_onset"]})
    for h in report["hypotheses"]:
        nodes.append({"id": h["id"], "type": "hypothesis", "label": h["title"], "status": h["status"], "role": h["role"], "kind": h["kind"]})
        edges.append({"source": h["id"], "target": h["candidate_resource_id"], "type": "about"})
        if h.get("related_resource_id"):
            edges.append({"source": h["id"], "target": h["related_resource_id"], "type": "about"})
        edges += [{"source": e, "target": h["id"], "type": "supports"} for e in h["supporting_evidence"]]
        edges += [{"source": e, "target": h["id"], "type": "contradicts"} for e in h["contradicting_evidence"]]
    for e in items:
        if e.id in used:
            nodes.append({"id": e.id, "type": "evidence", "label": e.summary[:80], "kind": e.kind, "resource_id": e.resource_id})
    return {"nodes": nodes, "edges": edges}


def fingerprint(report: dict[str, Any], topo: Topology) -> dict[str, Any]:
    """Learning Agent input: features used to find similar past incidents."""
    concl = report["conclusion"]
    root = next((h for h in report["hypotheses"] if h["id"] == concl.get("root_hypothesis_id")), None)
    features = {f"chain:{topo.resources[c['resource_id']]['kind']}" for c in concl["causal_chain"]}
    if root:
        features |= {f"root_kind:{root['kind']}", f"root_resource_kind:{topo.resources[root['candidate_resource_id']]['kind']}"}
    for t in report["timeline"]:
        if t["anomalous"]:
            features |= {f"term:{w.strip('.,:;()').lower()}" for w in t["summary"].split() if len(w) > 6 and not any(ch.isdigit() for ch in w)}
    return {"features": sorted(features), "rca_status": concl.get("final_status", concl["status"])}


def similar_incidents(db: Session, incident: Incident, min_similarity: float = 0.25) -> list[dict[str, Any]]:
    mine = set(incident.fingerprint.get("features", []))
    if not mine:
        return []
    out = []
    for other in db.scalars(select(Incident).where(Incident.tenant_id == incident.tenant_id, Incident.id != incident.id)):
        theirs = set(other.fingerprint.get("features", []))
        if not theirs:
            continue
        sim = len(mine & theirs) / len(mine | theirs)
        if sim >= min_similarity:
            out.append({"incident_id": other.id, "title": other.title, "status": other.status, "similarity": round(sim, 3),
                        "shared_features": sorted(mine & theirs)[:12], "outcome": other.fingerprint.get("outcome")})
    return sorted(out, key=lambda x: -x["similarity"])
