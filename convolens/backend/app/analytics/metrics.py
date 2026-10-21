"""Exact, parameterised SQL metrics over the conversation unit of analysis.

Every function returns dataset identity, the applied filters, the denominator, explicit unknown counts,
evidence identifiers and execution metadata. Only allowlisted fields can be grouped on.
"""
from __future__ import annotations

import statistics
import time
from collections import Counter, defaultdict
from datetime import datetime, time as dtime, timezone

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session

from app.analytics.taxonomy import ESCALATION, JOURNEY_LABELS, JOURNEY_STAGES, RESOLUTION, SENTIMENT, TOPIC_KEYS, TOPICS, topic_label
from app.models.orm import Analysis, Conversation, Dataset, Message
from app.models.schemas import Filters

GROUPABLE = {
    "primary_topic": (Conversation.primary_topic, TOPIC_KEYS, topic_label),
    "resolution_status": (Conversation.resolution_status, list(RESOLUTION), RESOLUTION.get),
    "sentiment_start": (Conversation.sentiment_start, list(SENTIMENT), SENTIMENT.get),
    "sentiment_end": (Conversation.sentiment_end, list(SENTIMENT), SENTIMENT.get),
    "escalation_requested": (Conversation.escalation_requested, list(ESCALATION), ESCALATION.get),
}


def evidence_id(conv_key: str, source_id: str, start: int | None = None, end: int | None = None) -> str:
    return f"{conv_key}/{source_id}" + (f"#{start}-{end}" if start is not None and end is not None else "")


def parse_evidence_id(eid: str) -> tuple[str, str, int | None, int | None]:
    conv, _, rest = eid.partition("/")
    src, _, span = rest.partition("#")
    if span:
        a, _, b = span.partition("-")
        return conv, src, int(a), int(b)
    return conv, src, None, None


def conditions(dataset_id: str, f: Filters | None) -> list:
    f = f or Filters()
    c = [Conversation.dataset_id == dataset_id]
    if f.topics:
        c.append(Conversation.primary_topic.in_(f.topics))
    if f.resolution:
        c.append(Conversation.resolution_status.in_(f.resolution))
    if f.sentiment_end:
        c.append(Conversation.sentiment_end.in_(f.sentiment_end))
    if f.escalation:
        c.append(Conversation.escalation_requested.in_(f.escalation))
    if f.brands:
        c.append(Conversation.brand.in_(f.brands))
    if f.conversation_keys:
        c.append(Conversation.key.in_(f.conversation_keys))
    if f.date_from:
        c.append(Conversation.started_at >= datetime.combine(f.date_from, dtime.min, tzinfo=timezone.utc))
    if f.date_to:
        c.append(Conversation.started_at <= datetime.combine(f.date_to, dtime.max, tzinfo=timezone.utc))
    if f.languages:
        c.append(exists().where(and_(Message.conversation_id == Conversation.id, Message.language.in_(f.languages))))
    return c


def _meta(t0: float, op: str, **kw) -> dict:
    return {"operation": op, "duration_ms": round((time.perf_counter() - t0) * 1000, 1), **kw}


def _scope(db: Session, dataset_id: str, f: Filters | None) -> dict:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise ValueError(f"Unknown dataset {dataset_id!r}")
    return {"dataset": {"id": ds.id, "name": ds.name, "kind": ds.kind, "synthetic": ds.synthetic,
                        "analysis": ds.active_analysis},
            "filters": (f or Filters()).model_dump(mode="json", exclude_defaults=True),
            "scope": (f or Filters()).describe()}


def denominator(db: Session, dataset_id: str, f: Filters | None) -> int:
    return db.scalar(select(func.count(Conversation.id)).where(*conditions(dataset_id, f))) or 0


def sample_evidence(db: Session, dataset_id: str, f: Filters | None, field: str | None = None, value: str | None = None,
                    limit: int = 3) -> list[dict]:
    """Deterministic evidence: first ``limit`` conversations by key, using validated spans supporting ``field``."""
    conds = conditions(dataset_id, f)
    if field and value is not None:
        conds.append(GROUPABLE[field][0] == value)
    rows = db.execute(select(Conversation.key, Conversation.analysis_id).where(*conds).order_by(Conversation.key).limit(limit * 10)).all()
    out: list[dict] = []
    seen_quotes: set[str] = set()
    for key, aid in rows:
        a = db.get(Analysis, aid) if aid else None
        spans = (a.fields.get("evidence") if a else None) or []
        want = {"primary_topic": "topic:", "resolution_status": "resolution_status", "escalation_requested": "escalation_requested",
                "sentiment_end": "sentiment", "sentiment_start": "sentiment"}.get(field or "", "")
        chosen = next((sp for sp in spans if sp.get("supports", "").startswith(want)), spans[0] if spans else None)
        if chosen and chosen["quote"].strip().lower() not in seen_quotes:
            seen_quotes.add(chosen["quote"].strip().lower())
            out.append({"id": evidence_id(key, chosen["message_id"], chosen.get("start"), chosen.get("end")),
                        "conversation_key": key, "message_id": chosen["message_id"], "quote": chosen["quote"],
                        "supports": chosen.get("supports")})
        if len(out) >= limit:
            break
    return out


def dataset_summary(db: Session, dataset_id: str, f: Filters | None = None) -> dict:
    t0 = time.perf_counter()
    conds = conditions(dataset_id, f)
    n = denominator(db, dataset_id, f)
    msgs = db.scalar(select(func.count(Message.id)).join(Conversation, Message.conversation_id == Conversation.id).where(*conds)) or 0
    span = db.execute(select(func.min(Conversation.started_at), func.max(Conversation.ended_at)).where(*conds)).one()
    ds = db.get(Dataset, dataset_id)
    m = ds.manifest or {}
    brands = db.execute(select(Conversation.brand, func.count()).where(*conds).group_by(Conversation.brand)
                        .order_by(func.count().desc()).limit(10)).all()
    return {
        **_scope(db, dataset_id, f),
        "denominator": n, "unit": "conversations",
        "messages": msgs,
        "time_range": {"from": span[0].isoformat() if span[0] else None, "to": span[1].isoformat() if span[1] else None},
        "support_accounts": [{"brand": b or "unknown", "count": c} for b, c in brands],
        "sampling": m.get("sampling", {}),
        "exclusions": m.get("exclusions", {}),
        "available_fields": ["primary_topic", "resolution_status", "sentiment_start", "sentiment_end",
                             "escalation_requested", "message language", "timestamps", "first response time"],
        "unavailable_fields": ["CSAT or ratings", "NPS", "revenue", "churn", "customer location", "agent identity",
                               "handle time outside Twitter", "follow-up outcomes after the thread ends"],
        "evidence_ids": [],
        "meta": _meta(t0, "dataset_summary"),
    }


def breakdown(db: Session, dataset_id: str, f: Filters | None, field: str, evidence_per_category: int = 2) -> dict:
    if field not in GROUPABLE:
        raise ValueError(f"Field {field!r} is not groupable")
    t0 = time.perf_counter()
    col, cats, labeler = GROUPABLE[field]
    conds = conditions(dataset_id, f)
    rows = dict(db.execute(select(col, func.count()).where(*conds).group_by(col)).all())
    n = sum(rows.values())
    items = []
    evidence: list[dict] = []
    for k in cats:
        c = rows.get(k, 0)
        if c == 0 and k not in ("unknown",):
            continue
        ev = sample_evidence(db, dataset_id, f, field, k, evidence_per_category) if c and k != "unknown" else []
        evidence.extend(ev)
        items.append({"key": k, "label": labeler(k), "count": c, "share": round(c / n, 4) if n else None,
                      "evidence_ids": [e["id"] for e in ev]})
    items.sort(key=lambda x: (x["key"] == "unknown", -x["count"]))
    unknown = rows.get("unknown", 0)
    return {**_scope(db, dataset_id, f), "field": field, "denominator": n, "unit": "conversations",
            "unknown": unknown, "items": items, "evidence": evidence, "evidence_ids": [e["id"] for e in evidence],
            "meta": _meta(t0, f"breakdown:{field}")}


def cross_tab(db: Session, dataset_id: str, f: Filters | None, row_field: str, col_field: str) -> dict:
    if row_field not in GROUPABLE or col_field not in GROUPABLE:
        raise ValueError("Field not groupable")
    t0 = time.perf_counter()
    rc, rcats, rlab = GROUPABLE[row_field]
    cc, ccats, clab = GROUPABLE[col_field]
    data = db.execute(select(rc, cc, func.count()).where(*conditions(dataset_id, f)).group_by(rc, cc)).all()
    grid: dict[str, Counter] = defaultdict(Counter)
    for r, c, n in data:
        grid[r][c] += n
    rows = []
    for r in rcats:
        if r not in grid:
            continue
        total = sum(grid[r].values())
        rows.append({"key": r, "label": rlab(r), "total": total,
                     "cells": [{"key": c, "label": clab(c), "count": grid[r].get(c, 0),
                                "share_of_row": round(grid[r].get(c, 0) / total, 4) if total else None} for c in ccats]})
    rows.sort(key=lambda x: (x["key"] == "unknown", -x["total"]))
    n = sum(r["total"] for r in rows)
    return {**_scope(db, dataset_id, f), "row_field": row_field, "col_field": col_field, "denominator": n,
            "unit": "conversations", "columns": [{"key": c, "label": clab(c)} for c in ccats], "rows": rows,
            "evidence_ids": [], "meta": _meta(t0, f"cross_tab:{row_field}x{col_field}")}


def timeseries(db: Session, dataset_id: str, f: Filters | None, grain: str = "week") -> dict:
    t0 = time.perf_counter()
    fmt = {"day": "%Y-%m-%d", "week": "%Y-W%W", "month": "%Y-%m"}.get(grain)
    if not fmt:
        raise ValueError("grain must be day, week or month")
    conds = conditions(dataset_id, f)
    bucket = func.strftime(fmt, Conversation.started_at)
    rows = db.execute(select(bucket, Conversation.primary_topic, func.count()).where(*conds)
                      .group_by(bucket, Conversation.primary_topic).order_by(bucket)).all()
    series: dict[str, Counter] = defaultdict(Counter)
    unknown_time = 0
    for b, topic, n in rows:
        if b is None:
            unknown_time += n
        else:
            series[b][topic] += n
    points = [{"bucket": b, "total": sum(c.values()), "by_topic": dict(c)} for b, c in sorted(series.items())]
    return {**_scope(db, dataset_id, f), "grain": grain, "points": points, "unknown_timestamp": unknown_time,
            "denominator": sum(p["total"] for p in points) + unknown_time, "unit": "conversations started",
            "caveat": "Counts of sampled conversations by start date. A seeded sample of a static export is not a "
                      "trend of total contact volume.",
            "evidence_ids": [], "meta": _meta(t0, f"timeseries:{grain}")}


def _characteristics(db: Session, dataset_id: str, f: Filters) -> dict:
    conds = conditions(dataset_id, f)
    convs = db.execute(select(Conversation.message_count, Conversation.customer_turns, Conversation.first_response_s,
                              Conversation.sentiment_start, Conversation.escalation_requested, Conversation.branch_count,
                              Conversation.primary_topic).where(*conds)).all()
    n = len(convs)
    if not n:
        return {"n": 0}
    frt = [c.first_response_s / 60 for c in convs if c.first_response_s is not None and c.first_response_s >= 0]
    neg = sum(1 for c in convs if c.sentiment_start == "negative")
    sk = sum(1 for c in convs if c.sentiment_start == "unknown")
    esc = sum(1 for c in convs if c.escalation_requested == "yes")
    ek = sum(1 for c in convs if c.escalation_requested == "unknown")
    topics = Counter(c.primary_topic for c in convs)
    return {
        "n": n,
        "mean_messages": round(sum(c.message_count for c in convs) / n, 2),
        "mean_customer_turns": round(sum(c.customer_turns for c in convs) / n, 2),
        "median_first_response_min": round(statistics.median(frt), 1) if frt else None,
        "first_response_known": len(frt),
        "negative_start": {"numerator": neg, "denominator": n - sk, "unknown": sk},
        "escalation_requested": {"numerator": esc, "denominator": n - ek, "unknown": ek},
        "branched_share": round(sum(1 for c in convs if c.branch_count) / n, 4),
        "top_topics": [{"key": k, "label": topic_label(k), "count": v} for k, v in topics.most_common(5)],
    }


def compare(db: Session, dataset_id: str, base: Filters | None, a: Filters, b: Filters, labels=("A", "B")) -> dict:
    t0 = time.perf_counter()
    base = base or Filters()

    def merge(x: Filters) -> Filters:
        d = base.model_dump()
        for k, v in x.model_dump().items():
            if v:
                d[k] = v
        return Filters(**d)

    fa, fb = merge(a), merge(b)
    ca, cb = _characteristics(db, dataset_id, fa), _characteristics(db, dataset_id, fb)
    ev = sample_evidence(db, dataset_id, fa, None, None, 2) + sample_evidence(db, dataset_id, fb, None, None, 2)
    return {**_scope(db, dataset_id, base), "segments": [
        {"label": labels[0], "filters": fa.model_dump(mode="json", exclude_defaults=True), "scope": fa.describe(), **ca},
        {"label": labels[1], "filters": fb.model_dump(mode="json", exclude_defaults=True), "scope": fb.describe(), **cb}],
        "denominator": ca.get("n", 0) + cb.get("n", 0), "unit": "conversations",
        "caveat": "Differences between segments are observed associations in this sample, not causes.",
        "evidence": ev, "evidence_ids": [e["id"] for e in ev], "meta": _meta(t0, "compare_segments")}


def topic_cooccurrence(db: Session, dataset_id: str, f: Filters | None) -> dict:
    t0 = time.perf_counter()
    rows = db.execute(select(Conversation.primary_topic, Conversation.secondary_topics, Conversation.subtheme)
                      .where(*conditions(dataset_id, f))).all()
    topic_n: Counter = Counter()
    sub_n: Counter = Counter()
    pairs: Counter = Counter()
    for p, sec, sub in rows:
        topic_n[p] += 1
        if sub:
            sub_n[(p, sub)] += 1
        for s in sec or []:
            if s != p:
                pairs[tuple(sorted((p, s)))] += 1
    return {**_scope(db, dataset_id, f), "denominator": len(rows), "unit": "conversations",
            "topics": [{"key": k, "label": topic_label(k), "count": v,
                        "definition": TOPICS.get(k, {}).get("definition", "No rule matched or language not covered." if k == "unknown" else "Conversation did not match a defined topic.")}
                       for k, v in topic_n.most_common()],
            "subthemes": [{"topic": t, "key": s, "label": s.replace("_", " ").capitalize(), "count": v} for (t, s), v in sub_n.most_common()],
            "edges": [{"source": a, "target": b, "count": v, "kind": "observed_co_occurrence"} for (a, b), v in pairs.most_common()],
            "evidence_ids": [], "meta": _meta(t0, "topic_cooccurrence")}


def journey(db: Session, dataset_id: str, f: Filters | None) -> dict:
    """Aggregate journey over actual reply edges (parent message stage -> reply message stage)."""
    t0 = time.perf_counter()
    conds = conditions(dataset_id, f)
    msgs = db.execute(select(Message.conversation_id, Message.source_id, Message.parent_source_id, Message.stage)
                      .join(Conversation, Message.conversation_id == Conversation.id).where(*conds)).all()
    by_conv: dict[int, dict[str, str]] = defaultdict(dict)
    parents: list[tuple[int, str | None, str]] = []
    for cid, sid, par, st in msgs:
        by_conv[cid][sid] = st or "unknown"
        parents.append((cid, par, sid))
    reach: Counter = Counter()
    for cid, stages in by_conv.items():
        for st in set(stages.values()):
            reach[st] += 1
    edges: Counter = Counter()
    for cid, par, sid in parents:
        if par and par in by_conv[cid]:
            edges[(by_conv[cid][par], by_conv[cid][sid])] += 1
    n = len(by_conv)
    missing_outcome = sum(1 for s in by_conv.values() if "outcome" not in s.values())
    return {**_scope(db, dataset_id, f), "denominator": n, "unit": "conversations",
            "stages": [{"key": k, "label": JOURNEY_LABELS[k], "conversations": reach.get(k, 0),
                        "missing": n - reach.get(k, 0)} for k in JOURNEY_STAGES],
            "transitions": [{"source": a, "target": b, "reply_edges": v} for (a, b), v in edges.most_common()],
            "missing_outcome_evidence": missing_outcome,
            "method": "Stages are inferred per message by rules (rules-v1); transitions follow actual reply links.",
            "evidence_ids": [], "meta": _meta(t0, "journey")}
