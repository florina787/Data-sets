"""Conversation X-Ray: a message-level diagnosis of one conversation.

Every finding is computed from message labels (act, sentiment, empathy, resolution)
and cites the message IDs it rests on, so the UI can synchronise the timeline and the
transcript in both directions. Nothing here is inferred by a model.
"""

from __future__ import annotations

from app.analytics.db import DATASET_SOURCES, AnalyticsDB
from app.analytics.trajectories import conversation_messages
from app.labeling.taxonomy import RELEVANT_RESOLUTIONS, TOPICS
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

EMPATHIC_ACTS = {"empathy_acknowledgement", "apology"}
CONCERN_ACTS = {"issue_report": "Reported the issue", "urgency": "Pressed for urgency", "waiting": "Still waiting",
                "escalation_request": "Asked to escalate"}
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _phase(i: int, n: int) -> str:
    if i < 2:
        return "opening"
    if i >= n - 2:
        return "closing"
    return "middle"


def _signal(kind: str, category: str, severity: str, title: str, detail: str, message_ids: list[str], turns: list[int]) -> dict:
    return {"kind": kind, "category": category, "severity": severity, "title": title, "detail": detail,
            "message_ids": message_ids, "turns": turns, "first_turn": min(turns) if turns else None}


def conversation_xray(db: AnalyticsDB, scope: Scope, conversation_id: str) -> AnalysisResult:
    params = {"conversation_id": conversation_id}
    msgs = conversation_messages(db, conversation_id)
    if msgs.empty:
        return AnalysisResult(operation="conversation_xray", params=params, scope=scope, status="insufficient_data",
                              uncertainty_notes=[f"Conversation {conversation_id} was not found."])
    conv = db.query("SELECT * FROM conversations WHERE conversation_id = ?", [conversation_id]).iloc[0]
    if conv["dataset_source"] not in DATASET_SOURCES[scope.dataset_mode]:
        return AnalysisResult(operation="conversation_xray", params=params, scope=scope, status="insufficient_data",
                              uncertainty_notes=[f"Conversation {conversation_id} is not part of the selected dataset mode ({scope.dataset_mode})."])

    rows = msgs.to_dict("records")
    n = len(rows)
    signals: list[dict] = []
    cust = [r for r in rows if r["speaker_role"] == "customer"]
    agent = [r for r in rows if r["speaker_role"] == "agent"]

    # --- escalation signals -----------------------------------------------------------------
    esc = [r for r in cust if r["act"] == "escalation_request"]
    if esc:
        signals.append(_signal("escalation_request", "escalation", "high", f"Customer asked to escalate ({len(esc)}×)",
                               "Explicit escalation request: the customer no longer trusts this channel to fix the issue.",
                               [r["message_id"] for r in esc], [int(r["turn_index"]) for r in esc]))
    urg = [r for r in cust if r["act"] == "urgency"]
    if urg:
        signals.append(_signal("urgency", "escalation", "medium" if len(urg) == 1 else "high", f"Urgency pressure ({len(urg)}×)",
                               "The customer stressed time pressure.", [r["message_id"] for r in urg], [int(r["turn_index"]) for r in urg]))

    # --- repeated concerns ------------------------------------------------------------------
    for act, label in CONCERN_ACTS.items():
        same = [r for r in cust if r["act"] == act]
        if len(same) >= 2:
            signals.append(_signal("repeated_concern", "repeated_concern", "high" if len(same) >= 3 else "medium",
                                   f"{label} {len(same)} times", "The same concern recurs: earlier replies did not settle it.",
                                   [r["message_id"] for r in same], [int(r["turn_index"]) for r in same]))
    seen: dict[str, list[dict]] = {}
    for r in cust:
        seen.setdefault((r["text"] or "").strip().lower(), []).append(r)
    for text, same in seen.items():
        if text and len(same) >= 2:
            signals.append(_signal("verbatim_repeat", "repeated_concern", "medium", f"Customer repeated the same message {len(same)}×",
                                   f"“{same[0]['text'][:90]}”", [r["message_id"] for r in same], [int(r["turn_index"]) for r in same]))
    fixed = [r for r in cust if r["act"] == "confirms_fixed"]
    if fixed:
        later_neg = [r for r in cust if r["turn_index"] > fixed[0]["turn_index"] and r["sentiment"] == "negative"]
        if later_neg:
            signals.append(_signal("reopened_after_fix", "repeated_concern", "high", "Problem resurfaced after the customer said it was fixed",
                                   "The customer confirmed a fix, then raised a negative message again: the fix may not have held.",
                                   [fixed[0]["message_id"]] + [r["message_id"] for r in later_neg],
                                   [int(fixed[0]["turn_index"])] + [int(r["turn_index"]) for r in later_neg]))

    # --- communication gaps -----------------------------------------------------------------
    unack = []
    for r in cust:
        if r["sentiment"] != "negative":
            continue
        reply = next((a for a in agent if a["turn_index"] > r["turn_index"]), None)
        if reply is not None and not reply["empathy"] and reply["act"] not in EMPATHIC_ACTS:
            unack.append((r, reply))
    if unack:
        signals.append(_signal("unacknowledged_negative", "communication_gap", "high" if len(unack) >= 2 else "medium",
                               f"{len(unack)} negative message(s) answered without acknowledgement",
                               "The next agent reply did not acknowledge the customer's frustration (no empathy or apology).",
                               [m["message_id"] for pair in unack for m in pair], [int(m["turn_index"]) for pair in unack for m in pair]))
    for act, label in (("hold_notice", "hold notices"), ("verification_request", "verification requests")):
        same = [r for r in agent if r["act"] == act]
        if len(same) >= 2:
            signals.append(_signal(f"repeated_{act}", "communication_gap", "medium", f"{len(same)} {label}",
                                   "Repeated procedural replies without progress.", [r["message_id"] for r in same], [int(r["turn_index"]) for r in same]))
    agent_text: dict[str, list[dict]] = {}
    for r in agent:
        agent_text.setdefault((r["text"] or "").strip().lower(), []).append(r)
    for text, same in agent_text.items():
        if text and len(same) >= 2:
            signals.append(_signal("scripted_repeat", "communication_gap", "low", f"Agent sent the same reply {len(same)}×",
                                   f"“{same[0]['text'][:90]}”", [r["message_id"] for r in same], [int(r["turn_index"]) for r in same]))
    res = [r for r in agent if r["act"] == "resolution"]
    fitting = RELEVANT_RESOLUTIONS.get(conv["topic"])  # same mapping as the resolution-fit analysis
    if res and fitting and res[-1]["resolution"] not in fitting:
        last = res[-1]
        signals.append(_signal("resolution_mismatch", "communication_gap", "high", "Closing action does not fit the issue",
                               f"Agent's action ({str(last['resolution']).replace('_', ' ')}) does not match a {TOPICS[conv['topic']].label.lower()} issue.",
                               [last["message_id"]], [int(last["turn_index"])]))
    last_c = cust[-1] if cust else None
    if last_c is not None and last_c["sentiment"] == "negative":
        signals.append(_signal("ends_unresolved", "outcome", "high", "Conversation ends with a negative customer message",
                               "No confirmation of a fix by the end of the transcript.", [last_c["message_id"]], [int(last_c["turn_index"])]))

    signals.sort(key=lambda s: (SEVERITY_ORDER[s["severity"]], s["first_turn"] if s["first_turn"] is not None else 0))
    flagged: dict[str, list[str]] = {}
    for s in signals:
        for mid in s["message_ids"]:
            flagged.setdefault(mid, []).append(s["kind"])

    timeline = []
    for i, r in enumerate(rows):
        timeline.append({"message_id": r["message_id"], "turn_index": int(r["turn_index"]), "speaker_role": r["speaker_role"],
                         "phase": _phase(i, n), "act": r["act"], "sentiment": r["sentiment"],
                         "sentiment_score": float(r["sentiment_score"]) if r["sentiment_score"] is not None else None,
                         "empathy": bool(r["empathy"]), "resolution": r["resolution"] if isinstance(r["resolution"], str) else None,
                         "text": r["text"], "signals": flagged.get(r["message_id"], [])})
    phases = []
    for ph in ("opening", "middle", "closing"):
        cs = [t for t in timeline if t["phase"] == ph and t["speaker_role"] == "customer" and t["sentiment_score"] is not None]
        if cs:
            phases.append({"phase": ph, "customer_messages": len(cs), "mean_sentiment": round(sum(t["sentiment_score"] for t in cs) / len(cs), 3),
                           "negative": sum(t["sentiment"] == "negative" for t in cs)})

    counts = {c: sum(s["category"] == c for s in signals) for c in ("escalation", "repeated_concern", "communication_gap", "outcome")}
    cust_scores = [float(r["sentiment_score"]) for r in cust if r["sentiment_score"] is not None]
    high = [s for s in signals if s["severity"] == "high"]
    unc = ["Signals come from deterministic message labels (template mapping), not from reading tone; treat them as pointers to review, "
           "not as a verdict on the agent.",
           "Turn order follows turn_index; timestamps in this dataset are not in turn order."]
    if len(cust) < 3:
        unc.insert(0, f"Only {len(cust)} customer message(s): too few to read a pattern.")
    return AnalysisResult(
        operation="conversation_xray", params=params, scope=scope, status="ok" if len(cust) >= 1 else "insufficient_data",
        metrics=[
            Metric(id="messages", label="Messages", value=n, unit="count"),
            Metric(id="customer_turns", label="Customer messages", value=len(cust), unit="count"),
            Metric(id="escalation_signals", label="Escalation signals", value=counts["escalation"], unit="count"),
            Metric(id="repeated_concerns", label="Repeated concerns", value=counts["repeated_concern"], unit="count"),
            Metric(id="communication_gaps", label="Communication gaps", value=counts["communication_gap"], unit="count"),
            Metric(id="high_severity", label="High-severity findings", value=len(high), unit="count"),
            Metric(id="final_score", label="Final customer sentiment", value=cust_scores[-1] if cust_scores else None, unit="sentiment"),
            Metric(id="topic", label="Topic", value=f"{conv['topic_label']} · {conv['product']}"),
        ],
        table=Table(columns=list(timeline[0].keys()), rows=timeline),
        series={"signals": Table(columns=["kind", "category", "severity", "title", "detail", "message_ids", "turns", "first_turn"], rows=signals),
                "phases": Table(columns=["phase", "customer_messages", "mean_sentiment", "negative"], rows=phases)},
        evidence_refs=list(dict.fromkeys(mid for s in high for mid in s["message_ids"]))[:8] or [timeline[-1]["message_id"]],
        method_notes=["Repeated concern: the same customer act (issue report, urgency, waiting, escalation) two or more times, or a verbatim repeat.",
                      "Unacknowledged negative message: the next agent reply carries no empathy or apology label.",
                      "Phases: first two messages = opening, last two = closing, the rest = middle."],
        uncertainty_notes=unc,
        coverage={"agent_id": conv["agent_id"], "topic": conv["topic"], "product": conv["product"], "sentiment": conv["sentiment"],
                  "date": str(conv["conversation_date"]), "signals": len(signals)},
    )
