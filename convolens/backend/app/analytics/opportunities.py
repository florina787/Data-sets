"""Improvement candidates with transparent scoring. Effort is only ever reviewer-entered."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.metrics import conditions, sample_evidence
from app.analytics.taxonomy import TOPICS, topic_label
from app.models.orm import Conversation, OpportunityReview
from app.models.schemas import Filters

INTERVENTIONS = {
    "refund_delay": "Publish refund timelines in the first reply and add a refund-status lookup to the support macro.",
    "unexpected_charge": "Review fee disclosure at checkout and give agents a duplicate-charge reversal macro.",
    "payment_failure": "Add payment-failure guidance to the help centre and route declined-payment cases to billing.",
    "late_delivery": "Proactively notify customers when tracking stalls and give agents carrier escalation guidance.",
    "missing_item": "Standardise the 'delivered but not received' investigation path with a clear replacement policy.",
    "damaged_item": "Introduce photo-based damage claims with a same-day replacement decision.",
    "password_reset": "Investigate password-reset email delivery and add an in-channel reset path.",
    "locked_account": "Review lock-out triggers introduced by recent updates and publish unlock steps.",
    "security_concern": "Create a priority route for suspected account compromise with a security checklist.",
    "crash_after_update": "Track crash reports by app version and publish known-issue notices with fixes.",
    "error_message": "Map frequent error codes to resolution articles linked in first replies.",
    "device_performance": "Collect device/version details up front and route performance regressions to engineering.",
    "outage": "Post proactive outage status updates in the support channel with expected restoration times.",
    "slow_speed": "Offer a self-service line test link in the first reply.",
    "signal_coverage": "Provide coverage-check guidance and an engineer-visit escalation path.",
    "delay_cancellation": "Send proactive disruption updates and rebooking options before customers ask.",
    "baggage": "Expose baggage-claim status updates and set expectations for delivery timelines.",
    "rebooking": "Give agents authority to rebook missed connections directly in-channel.",
    "cancel_request": "Offer an online cancellation path and confirm completion in-channel.",
    "switching_provider": "Review retention offers for customers stating they are switching.",
    "long_wait": "Publish expected response times and offer call-backs during peak hold times.",
    "no_response": "Monitor unanswered follow-ups and set a maximum follow-up response target.",
    "staff_conduct": "Review flagged interactions with team leads and refresh tone guidance.",
}
DEFAULT_WEIGHTS = {"frequency": 0.35, "severity": 0.35, "evidence": 0.2, "effort": 0.1}


def candidates(db: Session, dataset_id: str, f: Filters | None, weights: dict | None = None) -> dict:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    conds = conditions(dataset_id, f)
    rows = db.execute(select(Conversation.primary_topic, Conversation.subtheme, Conversation.resolution_status,
                             Conversation.escalation_requested, Conversation.sentiment_end).where(*conds)).all()
    total = len(rows)
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        if r.primary_topic in TOPICS:
            groups[(r.primary_topic, r.subtheme or "general")].append(r)
    reviews = {r.candidate_key: r for r in db.scalars(select(OpportunityReview).where(OpportunityReview.dataset_id == dataset_id))}
    out = []
    max_n = max((len(v) for v in groups.values()), default=1)
    for (topic, sub), rs in groups.items():
        n = len(rs)
        unresolved = sum(1 for r in rs if r.resolution_status == "unresolved_explicit")
        res_known = sum(1 for r in rs if r.resolution_status != "unknown")
        esc = sum(1 for r in rs if r.escalation_requested == "yes")
        esc_known = sum(1 for r in rs if r.escalation_requested != "unknown")
        neg = sum(1 for r in rs if r.sentiment_end == "negative")
        neg_known = sum(1 for r in rs if r.sentiment_end != "unknown")
        u_rate = unresolved / res_known if res_known else 0
        e_rate = esc / esc_known if esc_known else 0
        n_rate = neg / neg_known if neg_known else 0
        auto_sev = 1 + round(4 * min(1.0, 0.5 * u_rate + 0.3 * e_rate + 0.2 * n_rate) , 0)
        key = f"{topic}:{sub}"
        rv = reviews.get(key)
        severity = rv.severity if rv and rv.severity else int(auto_sev)
        sub_f = Filters(**{**(f.model_dump() if f else {}), "topics": [topic]})
        ev = sample_evidence(db, dataset_id, sub_f, "primary_topic", topic, 3)
        coverage = res_known / n if n else 0
        strength = "strong" if n >= 30 and len(ev) >= 3 and coverage >= 0.8 else "moderate" if n >= 10 and len(ev) >= 2 else "limited"
        strength_v = {"strong": 1.0, "moderate": 0.6, "limited": 0.25}[strength]
        effort = rv.effort if rv else None
        freq_norm = n / max_n
        parts = {"frequency": round(w["frequency"] * freq_norm, 4), "severity": round(w["severity"] * severity / 5, 4),
                 "evidence": round(w["evidence"] * strength_v, 4),
                 "effort": round(w["effort"] * (1 - (effort - 1) / 4), 4) if effort else None}
        score = round(sum(v for v in parts.values() if v is not None), 4)
        out.append({
            "key": key, "topic": topic, "topic_label": topic_label(topic), "subtheme": sub,
            "title": f"{topic_label(topic)}: {sub.replace('_', ' ')}",
            "intervention": INTERVENTIONS.get(sub, f"Review handling guidance for {topic_label(topic).lower()} conversations."),
            "proposed_department": TOPICS[topic]["department"],
            "frequency": {"numerator": n, "denominator": total, "share": round(n / total, 4) if total else None},
            "unresolved": {"numerator": unresolved, "denominator": res_known, "unknown": n - res_known},
            "escalation": {"numerator": esc, "denominator": esc_known, "unknown": n - esc_known},
            "negative_end": {"numerator": neg, "denominator": neg_known, "unknown": n - neg_known},
            "severity": severity, "severity_source": "reviewer" if rv and rv.severity else "rubric",
            "evidence_strength": strength, "evidence": ev, "evidence_ids": [e["id"] for e in ev],
            "effort": effort, "effort_source": (rv.effort_source if rv else None) or (None if effort is None else "reviewer"),
            "reviewer": rv.reviewer if rv else None,
            "score": score, "score_parts": parts,
            "score_complete": effort is not None,
        })
    out.sort(key=lambda x: -x["score"])
    return {"denominator": total, "unit": "conversations", "weights": w, "candidates": out,
            "rubric": {
                "severity": "1-5. Rubric = 1 + 4 x min(1, 0.5 x explicit-unresolved rate + 0.3 x escalation-request rate "
                            "+ 0.2 x negative-ending rate), each rate over known labels. A reviewer may override.",
                "evidence_strength": "strong: >=30 conversations, >=3 validated evidence spans, >=80% known outcomes; "
                                     "moderate: >=10 conversations and >=2 spans; otherwise limited.",
                "effort": "1 (small) to 5 (very large), entered by a reviewer only. Candidates without effort are "
                          "scored without the effort term and flagged as incomplete.",
                "score": "frequency_weight x (n / largest n) + severity_weight x severity/5 + evidence_weight x "
                         "strength (1, 0.6, 0.25) + effort_weight x (1 - (effort-1)/4).",
            }}
