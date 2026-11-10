"""Sentiment distribution and trend analytics."""

from __future__ import annotations

from app.analytics.db import AnalyticsDB, where
from app.analytics.stats import chi_square_independence, wilson_interval
from app.analytics.topics import NEGATIVE_RULE, _rows
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

SENTIMENT_ORDER = ["negative", "mixed", "neutral", "positive", "uncertain"]
GROUPS = {"topic": "topic_label", "domain": "domain", "month": "month", "language": "opening_language", "product": "product"}


def sentiment_distribution(db: AnalyticsDB, scope: Scope, group_by: str | None = None) -> AnalysisResult:
    w, p = where(scope)
    df = db.query(f"SELECT sentiment, COUNT(*) AS conversations FROM conversations c WHERE {w} GROUP BY sentiment", p)
    total = int(df["conversations"].sum()) if not df.empty else 0
    if not total:
        return AnalysisResult(operation="sentiment_distribution", scope=scope, status="insufficient_data", uncertainty_notes=["No conversations in scope."])
    df["share"] = df["conversations"] / total
    df["order"] = df["sentiment"].map(SENTIMENT_ORDER.index)
    df = df.sort_values("order").drop(columns="order")
    msg = db.query(
        f"""SELECT l.sentiment, COUNT(*) AS messages FROM message_labels l JOIN messages m USING (message_id)
            JOIN conversations c ON c.conversation_id = m.conversation_id
            WHERE {w} AND m.speaker_role = 'customer' GROUP BY l.sentiment""", p)
    msg_total = int(msg["messages"].sum())
    msg["share"] = msg["messages"] / msg_total
    series = {"customer_messages": Table(columns=["sentiment", "messages", "share"], rows=_rows(msg.round(4)))}
    unc: list[str] = []
    if group_by:
        col = GROUPS[group_by]
        g = db.query(
            f"""SELECT c.{col} AS name, c.sentiment, COUNT(*) AS conversations FROM conversations c WHERE {w}
                GROUP BY 1, 2 ORDER BY 1""", p)
        pivot = g.pivot_table(index="name", columns="sentiment", values="conversations", fill_value=0).reset_index()
        for s in SENTIMENT_ORDER:
            if s not in pivot:
                pivot[s] = 0
        pivot["total"] = pivot[SENTIMENT_ORDER].sum(axis=1)
        pivot["negative_rate"] = pivot["negative"] / pivot["total"]
        chi = chi_square_independence(pivot[["negative", "mixed", "neutral", "positive"]].astype(int).values.tolist())
        if chi["p_value"] is not None:
            unc.append(f"Sentiment mix {'does not differ' if chi['p_value'] >= 0.05 else 'differs'} significantly by {group_by} (chi-square p = {chi['p_value']}).")
        series["by_group"] = Table(columns=["name", *SENTIMENT_ORDER, "total", "negative_rate"], rows=_rows(pivot[["name", *SENTIMENT_ORDER, "total", "negative_rate"]].round(4)))
    neg = int(df.loc[df["sentiment"] == "negative", "conversations"].sum())
    return AnalysisResult(
        operation="sentiment_distribution", params={"group_by": group_by}, scope=scope,
        metrics=[Metric(id="conversations_in_scope", label="Conversations", value=total, unit="count"),
                 Metric(id="negative_rate_overall", label="Negative conversations", value=round(neg / total, 4), unit="percent", numerator=neg, denominator=total),
                 Metric(id="customer_messages", label="Customer messages", value=msg_total, unit="count")],
        table=Table(columns=["sentiment", "conversations", "share"], rows=_rows(df.round(4))),
        series=series,
        method_notes=[NEGATIVE_RULE, "'Mixed' means the customer expressed both positive and negative sentiment and the mean score is between -0.25 and 0.25."],
        uncertainty_notes=unc,
        coverage={"conversations": total},
    )


def sentiment_trend(db: AnalyticsDB, scope: Scope) -> AnalysisResult:
    # A trend needs every month, so the date window is deliberately not applied; other filters are.
    w, p = where(scope, skip={"window"})
    df = db.query(
        f"""SELECT c.month, COUNT(*) AS conversations, SUM((c.sentiment='negative')::INT) AS negative,
                   AVG(c.sentiment_score_mean) AS mean_sentiment, SUM(c.escalation_requests) AS escalation_requests
            FROM conversations c WHERE {w} AND c.month IS NOT NULL GROUP BY c.month ORDER BY c.month""", p)
    if df.empty:
        return AnalysisResult(operation="sentiment_trend", scope=scope, status="insufficient_data", uncertainty_notes=["No dated conversations in scope."])
    df["negative_rate"] = df["negative"] / df["conversations"]
    ci = [wilson_interval(int(x), int(n)) for x, n in zip(df["negative"], df["conversations"])]
    df["rate_ci_low"], df["rate_ci_high"] = [c[0] for c in ci], [c[1] for c in ci]
    unc = []
    if len(df) < 3:
        unc.append("Fewer than three months of data: a trend cannot be established.")
    else:
        first, last = df.iloc[0], df.iloc[-1]
        overlap = not (last["rate_ci_low"] > first["rate_ci_high"] or last["rate_ci_high"] < first["rate_ci_low"])
        unc.append(f"Negative rate moved from {first['negative_rate']:.1%} ({first['month']}) to {last['negative_rate']:.1%} ({last['month']}); "
                   + ("the 95% intervals overlap, so this is not a reliable trend." if overlap else "the 95% intervals do not overlap."))
    cols = ["month", "conversations", "negative", "negative_rate", "rate_ci_low", "rate_ci_high", "mean_sentiment", "escalation_requests"]
    return AnalysisResult(
        operation="sentiment_trend", params={}, scope=scope,
        metrics=[Metric(id="months", label="Months", value=len(df), unit="count"),
                 Metric(id="latest_negative_rate", label=f"Negative rate {df.iloc[-1]['month']}", value=round(float(df.iloc[-1]['negative_rate']), 4), unit="percent",
                        numerator=int(df.iloc[-1]["negative"]), denominator=int(df.iloc[-1]["conversations"]))],
        table=Table(columns=cols, rows=_rows(df[cols].round(4))),
        method_notes=[NEGATIVE_RULE, "Months are assigned by each conversation's earliest timestamp."],
        uncertainty_notes=unc,
        coverage={"conversations": int(df["conversations"].sum())},
    )
