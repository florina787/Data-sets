"""Turn-by-turn sentiment trajectory of a single conversation."""

from __future__ import annotations

import pandas as pd

from app.analytics.db import AnalyticsDB, where
from app.analytics.topics import _rows
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

TURNING_POINT_DELTA = 0.8
MIN_CUSTOMER_TURNS = 3


def conversation_messages(db: AnalyticsDB, conversation_id: str) -> pd.DataFrame:
    return db.query(
        """SELECT m.message_id, m.conversation_id, m.turn_index, m.timestamp, m.speaker_role, m.masked_text AS text,
                  m.noise_token_count, m.source_reference, l.act, l.sentiment, l.sentiment_score, l.empathy, l.resolution,
                  l.language, l.method, l.confidence
           FROM messages m JOIN message_labels l USING (message_id)
           WHERE m.conversation_id = ? ORDER BY m.turn_index""",
        [conversation_id],
    )


def suggest_conversations(db: AnalyticsDB, scope: Scope, k: int = 3) -> list[dict]:
    """Conversations with the largest customer sentiment swing, as starting points."""
    w, p = where(scope)
    df = db.query(
        f"""SELECT conversation_id, topic_label, product, sentiment, first_followup_score, last_customer_score,
                   (last_customer_score - first_followup_score) AS swing
            FROM conversations c WHERE {w} AND first_followup_score IS NOT NULL
            ORDER BY ABS(last_customer_score - first_followup_score) DESC, conversation_id LIMIT ?""", p + [k])
    return _rows(df.round(3))


def sentiment_trajectory(db: AnalyticsDB, scope: Scope, conversation_id: str | None) -> AnalysisResult:
    if not conversation_id:
        sugg = suggest_conversations(db, scope)
        return AnalysisResult(
            operation="sentiment_trajectory", scope=scope, status="insufficient_data",
            table=Table(columns=list(sugg[0].keys()) if sugg else [], rows=sugg),
            evidence_refs=[s["conversation_id"] for s in sugg],
            uncertainty_notes=["No conversation was selected. Pick one in Conversation Explorer or mention its ID (e.g. C0000006). "
                               "The conversations listed have the largest customer sentiment swings."])
    msgs = conversation_messages(db, conversation_id)
    if msgs.empty:
        return AnalysisResult(operation="sentiment_trajectory", params={"conversation_id": conversation_id}, scope=scope, status="insufficient_data",
                              uncertainty_notes=[f"Conversation {conversation_id} was not found."])
    conv = db.query("SELECT * FROM conversations WHERE conversation_id = ?", [conversation_id]).iloc[0]
    if conv["dataset_source"] not in {"original": ["original"], "synthetic": ["synthetic_demo"], "combined": ["original", "synthetic_demo"]}[scope.dataset_mode]:
        return AnalysisResult(operation="sentiment_trajectory", params={"conversation_id": conversation_id}, scope=scope, status="insufficient_data",
                              uncertainty_notes=[f"Conversation {conversation_id} is not part of the selected dataset mode ({scope.dataset_mode})."])
    cust = msgs[msgs["speaker_role"] == "customer"].copy()
    cust["step"] = range(1, len(cust) + 1)
    cust["rolling_mean"] = cust["sentiment_score"].expanding().mean().round(3)
    cust["delta"] = cust["sentiment_score"].diff()

    turning: list[dict] = []
    for _, r in cust[cust["delta"].abs() >= TURNING_POINT_DELTA].iterrows():
        prev_agent = msgs[(msgs["speaker_role"] == "agent") & (msgs["turn_index"] < r["turn_index"])].tail(1)
        turning.append({
            "turn_index": int(r["turn_index"]), "message_id": r["message_id"], "direction": "improved" if r["delta"] > 0 else "worsened",
            "delta": round(float(r["delta"]), 2), "customer_text": r["text"],
            "preceding_agent_text": prev_agent["text"].iloc[0] if len(prev_agent) else None,
            "preceding_agent_message_id": prev_agent["message_id"].iloc[0] if len(prev_agent) else None,
        })
    unc: list[str] = []
    status = "ok"
    if len(cust) < MIN_CUSTOMER_TURNS:
        status = "insufficient_data"
        unc.append(f"Only {len(cust)} customer message(s): a meaningful trajectory cannot be inferred.")
    unc.append("Turn order follows turn_index; timestamps in this dataset are not in turn order and are not used for sequencing.")
    unc.append("Scores come from a fixed mapping of message templates to sentiment (-1 to 1); they are ordinal, not calibrated probabilities.")
    first, last = cust.iloc[1] if len(cust) > 1 else cust.iloc[0], cust.iloc[-1]
    rows = msgs.copy()
    rows["timestamp"] = rows["timestamp"].astype(str)
    cols = ["message_id", "turn_index", "speaker_role", "text", "act", "sentiment", "sentiment_score", "empathy", "resolution", "timestamp", "source_reference"]
    return AnalysisResult(
        operation="sentiment_trajectory",
        params={"conversation_id": conversation_id},
        scope=scope,
        status=status,
        metrics=[
            Metric(id="customer_turns", label="Customer messages", value=len(cust), unit="count"),
            Metric(id="opening_score", label="Opening sentiment", value=float(cust.iloc[0]["sentiment_score"]), unit="sentiment"),
            Metric(id="first_followup_score", label="First follow-up sentiment", value=float(first["sentiment_score"]), unit="sentiment"),
            Metric(id="final_score", label="Final customer sentiment", value=float(last["sentiment_score"]), unit="sentiment"),
            Metric(id="net_change", label="Net change (first follow-up → final)", value=round(float(last["sentiment_score"] - first["sentiment_score"]), 2), unit="sentiment"),
            Metric(id="turning_points", label="Turning points", value=len(turning), unit="count"),
            Metric(id="conversation_sentiment", label="Overall label", value=str(conv["sentiment"])),
            Metric(id="topic", label="Topic", value=f"{conv['topic_label']} · {conv['product']}"),
        ],
        table=Table(columns=cols, rows=_rows(rows[cols])),
        series={
            "trajectory": Table(columns=["step", "turn_index", "message_id", "sentiment", "sentiment_score", "rolling_mean", "act", "text"],
                                rows=_rows(cust[["step", "turn_index", "message_id", "sentiment", "sentiment_score", "rolling_mean", "act", "text"]])),
            "turning_points": Table(columns=list(turning[0].keys()) if turning else [], rows=turning),
        },
        evidence_refs=[t["message_id"] for t in turning] or [cust.iloc[-1]["message_id"]],
        method_notes=[f"A turning point is a change of at least {TURNING_POINT_DELTA} in sentiment score between consecutive customer messages."],
        uncertainty_notes=unc,
        coverage={"messages": len(msgs), "agent_id": conv["agent_id"], "topic": conv["topic"], "product": conv["product"]},
    )
