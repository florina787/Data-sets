"""Dataset coverage, resolution quality and single-conversation detail."""

from __future__ import annotations

from app.analytics.db import AnalyticsDB, where
from app.analytics.time_windows import available_months, data_range
from app.analytics.topics import _rows
from app.analytics.trajectories import conversation_messages
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table


def dataset_overview(db: AnalyticsDB, scope: Scope) -> AnalysisResult:
    w, p = where(scope)
    row = db.query(
        f"""SELECT COUNT(*) AS conversations, SUM(message_count) AS messages, COUNT(DISTINCT agent_id) AS agents,
                   COUNT(DISTINCT topic) AS topics, COUNT(DISTINCT product) AS products,
                   SUM((processing_status='labelled')::INT) AS labelled, SUM((processing_status<>'labelled')::INT) AS provisional,
                   AVG((sentiment='negative')::INT) AS negative_rate
            FROM conversations c WHERE {w}""", p).iloc[0]
    meta = db.metadata()
    months = available_months(db, scope.dataset_mode)
    lo, hi = data_range(db, scope.dataset_mode)
    methods = db.query(
        f"""SELECT l.method, COUNT(*) AS messages FROM message_labels l JOIN conversations c USING (conversation_id) WHERE {w} GROUP BY 1""", p)
    sources = db.query("SELECT dataset_source, COUNT(*) AS conversations FROM conversations GROUP BY 1 ORDER BY 1")
    n = int(row["conversations"] or 0)
    return AnalysisResult(
        operation="dataset_overview", scope=scope,
        metrics=[
            Metric(id="conversations_in_scope", label="Conversations", value=n, unit="count"),
            Metric(id="messages", label="Messages", value=int(row["messages"] or 0), unit="count"),
            Metric(id="agents", label="Agent IDs", value=int(row["agents"] or 0), unit="count"),
            Metric(id="topics", label="Issue topics", value=int(row["topics"] or 0), unit="count"),
            Metric(id="products", label="Products", value=int(row["products"] or 0), unit="count"),
            Metric(id="label_coverage", label="Fully labelled conversations", value=round(int(row["labelled"] or 0) / n, 4) if n else None,
                   unit="percent", numerator=int(row["labelled"] or 0), denominator=n),
            Metric(id="negative_rate_overall", label="Negative conversations", value=round(float(row["negative_rate"]), 4) if n else None, unit="percent"),
            Metric(id="date_range", label="Date range", value=f"{lo:%d %b %Y} – {hi:%d %b %Y}" if lo is not None else "n/a"),
        ],
        table=Table(columns=["month", "conversations"], rows=_rows(months[["month", "conversations"]])),
        series={"label_methods": Table(columns=["method", "messages"], rows=_rows(methods)),
                "dataset_sources": Table(columns=["dataset_source", "conversations"], rows=_rows(sources))},
        method_notes=[f"Pipeline {meta['pipeline_version']}, taxonomy {meta['taxonomy_version']}, labeller {meta['labeler_version']}, built {meta['built_at'][:19]}Z."],
        coverage={"conversations": n, "label_source": meta["label_coverage"]["label_source"]},
    )


def resolution_quality(db: AnalyticsDB, scope: Scope) -> AnalysisResult:
    w, p = where(scope)
    df = db.query(
        f"""SELECT topic_label, final_resolution, COUNT(*) AS conversations,
                   SUM(CASE WHEN resolution_relevant THEN 1 ELSE 0 END) AS fitting
            FROM conversations c WHERE {w} AND final_resolution IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2""", p)
    if df.empty:
        return AnalysisResult(operation="resolution_quality", scope=scope, status="insufficient_data", uncertainty_notes=["No resolutions in scope."])
    t = db.query(
        f"""SELECT topic_label, COUNT(*) AS conversations,
                   AVG(CASE WHEN resolution_relevant IS NULL THEN NULL ELSE (NOT resolution_relevant)::INT END) AS misfit_rate,
                   AVG(confirmed_fixed::INT) AS confirmed_fixed_rate, AVG(ends_negative::INT) AS ends_negative_rate
            FROM conversations c WHERE {w} GROUP BY 1 ORDER BY misfit_rate DESC NULLS LAST""", p)
    assessable = db.query(
        f"""SELECT COUNT(*) AS n, SUM((NOT resolution_relevant)::INT) AS misfit FROM conversations c WHERE {w} AND resolution_relevant IS NOT NULL""", p).iloc[0]
    n, misfit = int(assessable["n"] or 0), int(assessable["misfit"] or 0)
    return AnalysisResult(
        operation="resolution_quality", scope=scope,
        metrics=[Metric(id="misfit_rate", label="Closing action does not fit the issue", value=round(misfit / n, 4) if n else None, unit="percent",
                        numerator=misfit, denominator=n)],
        table=Table(columns=["topic_label", "conversations", "misfit_rate", "confirmed_fixed_rate", "ends_negative_rate"], rows=_rows(t.round(4))),
        series={"matrix": Table(columns=["topic_label", "final_resolution", "conversations", "fitting"], rows=_rows(df))},
        method_notes=["Fit uses the documented issue→action mapping in ASSUMPTIONS.md; general help requests are excluded as not assessable."],
        uncertainty_notes=["In this synthetic dataset the agent's closing action appears unrelated to the issue raised, so misfit rates are high everywhere; "
                           "this is a property of the data generator and worth flagging to the data owner."],
        coverage={"assessable_conversations": n},
    )


def conversation_detail(db: AnalyticsDB, scope: Scope, conversation_id: str) -> AnalysisResult:
    msgs = conversation_messages(db, conversation_id)
    if msgs.empty:
        return AnalysisResult(operation="conversation_detail", params={"conversation_id": conversation_id}, scope=scope, status="insufficient_data",
                              uncertainty_notes=[f"Conversation {conversation_id} was not found."])
    conv = db.query("SELECT * FROM conversations WHERE conversation_id = ?", [conversation_id]).iloc[0]
    msgs["timestamp"] = msgs["timestamp"].astype(str)
    cols = ["message_id", "turn_index", "speaker_role", "text", "act", "sentiment", "sentiment_score", "empathy", "resolution", "timestamp", "source_reference"]
    return AnalysisResult(
        operation="conversation_detail", params={"conversation_id": conversation_id}, scope=scope,
        metrics=[Metric(id="topic", label="Topic", value=str(conv["topic_label"])), Metric(id="product", label="Product", value=str(conv["product"])),
                 Metric(id="agent", label="Agent", value=str(conv["agent_id"])), Metric(id="sentiment", label="Sentiment", value=str(conv["sentiment"])),
                 Metric(id="final_resolution", label="Agent's closing action", value=str(conv["final_resolution"])),
                 Metric(id="resolution_relevant", label="Closing action fits issue", value=str(conv["resolution_relevant"])),
                 Metric(id="messages", label="Messages", value=int(conv["message_count"]), unit="count")],
        table=Table(columns=cols, rows=_rows(msgs[cols])),
        evidence_refs=[conversation_id],
        coverage={"messages": len(msgs)},
    )


def list_conversations(db: AnalyticsDB, scope: Scope, limit: int = 25, order: str = "most_negative") -> AnalysisResult:
    w, p = where(scope)
    order_sql = {"most_negative": "sentiment_score_mean ASC, escalation_requests DESC", "most_positive": "sentiment_score_mean DESC",
                 "recent": "start_timestamp DESC"}[order]
    total = int(db.scalar(f"SELECT COUNT(*) FROM conversations c WHERE {w}", p) or 0)
    df = db.query(
        f"""SELECT conversation_id, CAST(start_timestamp AS DATE) AS date, agent_id, topic_label, product, sentiment,
                   ROUND(sentiment_score_mean, 3) AS mean_sentiment, escalation_requests, final_resolution, resolution_relevant, ends_negative
            FROM conversations c WHERE {w} ORDER BY {order_sql}, conversation_id LIMIT ?""", p + [limit])
    df["date"] = df["date"].astype(str)
    neg = int(db.scalar(f"SELECT SUM((sentiment='negative')::INT) FROM conversations c WHERE {w}", p) or 0)
    return AnalysisResult(
        operation="list_conversations", params={"limit": limit, "order": order}, scope=scope,
        metrics=[Metric(id="conversations_in_scope", label="Matching conversations", value=total, unit="count"),
                 Metric(id="shown", label="Shown", value=len(df), unit="count"),
                 Metric(id="negative_in_scope", label="Negative among matches", value=neg, unit="count", numerator=neg, denominator=total)],
        table=Table(columns=list(df.columns), rows=_rows(df)),
        evidence_refs=df["conversation_id"].head(5).tolist(),
        method_notes=[f"Ordered by {order.replace('_', ' ')}; showing up to {limit}."],
        coverage={"conversations": total},
        status="ok" if total else "insufficient_data",
        uncertainty_notes=[] if total else ["No conversations match these filters."],
    )
