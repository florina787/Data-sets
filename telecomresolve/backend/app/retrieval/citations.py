"""Citation resolution and validation.

A citation is valid when (1) its source record exists within the tenant,
(2) the recorded version/excerpt still matches the source, and (3) for
hypotheses, the cited item carries the rule tag for that category.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.orm import (
    Case, DiagnosticSample, Equipment, EvidenceSnapshot, Hypothesis, Incident, KnowledgeChunk,
    Recommendation, ServiceAssetMapping, SupportInteraction,
)


def _samples(db: Session, tenant_id: str, ids: list[str]) -> list[DiagnosticSample]:
    if not ids:
        return []
    return list(db.scalars(select(DiagnosticSample).where(DiagnosticSample.id.in_(ids),
                                                          DiagnosticSample.tenant_id == tenant_id)
                           .order_by(DiagnosticSample.collected_at)))


def resolve(db: Session, tenant_id: str, item: dict) -> dict:
    """Return {'ok': bool, 'problem': str|None, 'record': dict} for one evidence item."""
    st, sid = item["source_type"], item["source_id"]
    rec: dict = {}
    problem = None
    if st == "knowledge":
        chunk = db.get(KnowledgeChunk, sid)
        if chunk is None:
            problem = "knowledge chunk missing"
        elif chunk.version != item["source_version"]:
            problem = f"document version changed ({item['source_version']} -> {chunk.version})"
        elif item["excerpt"] not in chunk.text:
            problem = "excerpt not found in source"
        else:
            rec = {"document_id": chunk.document_id, "heading": chunk.heading, "text": chunk.text,
                   "char_start": chunk.char_start, "char_end": chunk.char_end}
    elif st == "diagnostic_series":
        from ..agents.evidence import series_stats

        ids = item["data"].get("sample_ids", [])
        rows = _samples(db, tenant_id, ids)
        if len(rows) != len(ids):
            problem = "one or more cited samples missing"
        else:
            metric = item["data"].get("metric")
            value = item["data"].get("value")
            stats = series_stats(rows)
            recomputed = stats.get(metric) if metric in stats else None
            if metric in stats and recomputed != value:
                problem = f"recomputed {metric}={recomputed} differs from cited {value}"
            rec = {"samples": [_sample_dict(r) for r in rows], "metric": metric, "recomputed": recomputed}
    elif st == "diagnostic_sample":
        row = db.scalar(select(DiagnosticSample).where(DiagnosticSample.id == sid,
                                                       DiagnosticSample.tenant_id == tenant_id))
        if row is None and not sid.endswith(":on_demand"):
            problem = "sample missing"
        rec = _sample_dict(row) if row else {"note": "on-demand test result (unavailable)"}
    elif st == "incident":
        inc = db.scalar(select(Incident).where(Incident.id == sid, Incident.tenant_id == tenant_id))
        if inc is None:
            problem = "incident missing"
        else:
            rec = {"id": inc.id, "title": inc.title, "status": inc.status, "asset_id": inc.asset_id,
                   "started_at": inc.started_at.isoformat(), "ended_at": inc.ended_at.isoformat() if inc.ended_at else None,
                   "estimated_restoration_at": inc.estimated_restoration_at.isoformat() if inc.estimated_restoration_at else None,
                   "status_history": inc.status_history, "updated_at": inc.updated_at.isoformat()}
    elif st == "service_mapping":
        m = db.scalar(select(ServiceAssetMapping).where(ServiceAssetMapping.id == sid,
                                                        ServiceAssetMapping.tenant_id == tenant_id))
        problem = None if m else "mapping missing"
        if m:
            rec = {"id": m.id, "service_id": m.service_id, "asset_id": m.asset_id, "port": m.port,
                   "valid_from": m.valid_from.isoformat()}
    elif st == "support_interaction":
        h = db.scalar(select(SupportInteraction).where(SupportInteraction.id == sid,
                                                       SupportInteraction.tenant_id == tenant_id))
        problem = None if h else "interaction missing"
        if h:
            rec = {"id": h.id, "channel": h.channel, "occurred_at": h.occurred_at.isoformat(),
                   "summary": h.summary, "notes": h.notes, "actions_taken": h.actions_taken,
                   "outcome": h.outcome, "author_type": h.author_type}
    elif st == "equipment":
        e = db.scalar(select(Equipment).where(Equipment.id == sid, Equipment.tenant_id == tenant_id))
        problem = None if e else "equipment missing"
        if e:
            rec = {"id": e.id, "model": e.model, "firmware": e.firmware}
    elif st == "customer_statement":
        c = db.scalar(select(Case).where(Case.id == sid, Case.tenant_id == tenant_id))
        problem = None if c else "case missing"
        if c:
            rec = {"case_id": c.id, "complaint_text": c.complaint_text}
    elif st == "peer_health":
        rec = item.get("data", {})  # aggregate computed at retrieval time; recorded in the snapshot
    else:
        problem = f"unknown source type {st}"
    return {"ok": problem is None, "problem": problem, "record": rec}


def _sample_dict(r: DiagnosticSample) -> dict:
    return {"id": r.id, "collected_at": r.collected_at.isoformat(), "source": r.source,
            "link_state": r.link_state, "loss_of_signal_events": r.loss_of_signal_events,
            "link_retrains": r.link_retrains, "packet_loss_pct": r.packet_loss_pct, "latency_ms": r.latency_ms,
            "snr_margin_db": r.snr_margin_db, "crc_errors": r.crc_errors, "cpe_uptime_s": r.cpe_uptime_s,
            "cpe_unexpected_reboots": r.cpe_unexpected_reboots, "interval_minutes": r.interval_minutes,
            "simulated_post_action": r.simulated_post_action}


def validate_case(db: Session, tenant_id: str, case_id: str) -> dict:
    """Validate every citation used by the case's hypotheses and recommendations."""
    snaps = db.scalars(select(EvidenceSnapshot).where(EvidenceSnapshot.case_id == case_id,
                                                      EvidenceSnapshot.tenant_id == tenant_id)).all()
    checked, failures = 0, []
    for snap in snaps:
        items = {i["ref_id"]: i for i in snap.bundle["items"]}
        used: set[str] = set()
        for h in db.scalars(select(Hypothesis).where(Hypothesis.snapshot_id == snap.id)):
            for r in h.supporting_refs:
                used.add(r)
                if r not in items:
                    failures.append({"snapshot": snap.id, "ref": r, "problem": "cited ref not in snapshot"})
                elif h.category not in items[r]["supports"]:
                    failures.append({"snapshot": snap.id, "ref": r,
                                     "problem": f"does not support {h.category}"})
        for rec in db.scalars(select(Recommendation).where(Recommendation.snapshot_id == snap.id)):
            used.update(rec.evidence_refs)
            for rr in rec.refused_requests:
                used.update(rr.get("citations", []))
        for r in sorted(used):
            if r not in items:
                failures.append({"snapshot": snap.id, "ref": r, "problem": "cited ref not in snapshot"})
                continue
            checked += 1
            res = resolve(db, tenant_id, items[r])
            if not res["ok"]:
                failures.append({"snapshot": snap.id, "ref": r, "problem": res["problem"]})
    return {"checked": checked, "failures": failures, "all_resolve": not failures}
