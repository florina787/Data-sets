"""Topic analytics. Counting rule: each conversation has exactly one primary topic,
taken from the customer's opening message, and is counted once."""

from __future__ import annotations

import pandas as pd

from app.analytics.db import AnalyticsDB, where
from app.analytics.stats import chi_square_independence, two_proportion_test, wilson_interval
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

DIMENSIONS = {"topic": "topic_label", "product": "product", "domain": "domain"}
COUNTING_RULE = "Each conversation is counted once, under the primary topic of the customer's opening message."
NEGATIVE_RULE = "A conversation is negative when the mean sentiment score of its customer turns is -0.25 or lower."


def _rows(df: pd.DataFrame) -> list[dict]:
    return [{k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in r.items()} for r in df.to_dict("records")]


def representative_conversations(db: AnalyticsDB, scope: Scope, column: str, value: str, k: int = 3, sentiment: str | None = "negative") -> list[str]:
    """Deterministic evidence choice: the most negative conversations in the group (ties by id)."""
    w, p = where(scope)
    extra = " AND c.sentiment = ?" if sentiment else ""
    df = db.query(
        f"SELECT conversation_id FROM conversations c WHERE {w} AND c.{column} = ?{extra} "
        f"ORDER BY sentiment_score_mean ASC, escalation_requests DESC, conversation_id LIMIT ?",
        p + [value] + ([sentiment] if sentiment else []) + [k],
    )
    return df["conversation_id"].tolist()


def topic_sentiment_table(db: AnalyticsDB, scope: Scope, dimension: str = "topic") -> pd.DataFrame:
    col = DIMENSIONS[dimension]
    key = "topic" if dimension == "topic" else col
    w, p = where(scope)
    df = db.query(
        f"""SELECT c.{col} AS name, MIN(c.{key}) AS key, COUNT(*) AS conversations,
                   SUM((c.sentiment='negative')::INT) AS negative,
                   SUM((c.sentiment='mixed')::INT) AS mixed,
                   SUM((c.sentiment='positive')::INT) AS positive,
                   SUM((c.sentiment='neutral')::INT) AS neutral,
                   SUM(c.escalation_requests) AS escalation_requests,
                   AVG(c.sentiment_score_mean) AS mean_sentiment
            FROM conversations c WHERE {w} AND c.{col} IS NOT NULL GROUP BY c.{col}""",
        p,
    )
    if df.empty:
        return df
    total_neg = int(df["negative"].sum())
    df["negative_rate"] = df["negative"] / df["conversations"]
    ci = [wilson_interval(int(x), int(n)) for x, n in zip(df["negative"], df["conversations"])]
    df["rate_ci_low"] = [c[0] for c in ci]
    df["rate_ci_high"] = [c[1] for c in ci]
    df["share_of_negative"] = df["negative"] / total_neg if total_neg else 0.0
    return df


def rank_negative_topics(db: AnalyticsDB, scope: Scope, top_n: int = 5, dimension: str = "topic", rank_by: str = "count",
                         min_conversations: int = 20) -> AnalysisResult:
    df = topic_sentiment_table(db, scope, dimension)
    if df.empty:
        return AnalysisResult(operation="rank_negative_topics", scope=scope, status="insufficient_data",
                              uncertainty_notes=["No conversations match the selected scope."])
    total = int(df["conversations"].sum())
    total_neg = int(df["negative"].sum())
    by_count = df.sort_values(["negative", "negative_rate", "name"], ascending=[False, False, True]).reset_index(drop=True)
    by_rate = df[df["conversations"] >= min_conversations].sort_values(["negative_rate", "negative", "name"], ascending=[False, False, True]).reset_index(drop=True)
    ranked = by_count if rank_by == "count" else by_rate
    ranked = ranked.copy()
    ranked["rank"] = range(1, len(ranked) + 1)
    rate_rank = {n: i + 1 for i, n in enumerate(by_rate["name"])}
    ranked["rank_by_rate"] = ranked["name"].map(rate_rank)
    top = ranked.head(top_n)

    chi = chi_square_independence([[int(a), int(b)] for a, b in zip(df["negative"], df["conversations"] - df["negative"])])
    notes = [COUNTING_RULE, NEGATIVE_RULE,
             f"Ranked by {'number of negative conversations' if rank_by == 'count' else 'negative rate (groups with at least ' + str(min_conversations) + ' conversations)'}."]
    unc: list[str] = []
    if chi["p_value"] is not None:
        if chi["p_value"] >= 0.05:
            unc.append(f"The negative rate does not differ significantly across {dimension}s (chi-square p = {chi['p_value']}). "
                       "Rankings mostly reflect how many conversations each group has, so treat small gaps between ranks as noise.")
        else:
            unc.append(f"Negative rate differs across {dimension}s beyond chance (chi-square p = {chi['p_value']}).")
    if len(top) >= 2:
        a, b = top.iloc[0], top.iloc[1]
        t = two_proportion_test(int(a["negative"]), int(a["conversations"]), int(b["negative"]), int(b["conversations"]))
        if t["p_value"] is not None and t["p_value"] >= 0.05:
            unc.append(f"#1 ({a['name']}) and #2 ({b['name']}) have overlapping uncertainty in negative rate (p = {t['p_value']}).")
    key = "negative" if rank_by == "count" else "negative_rate"
    if len(ranked) > top_n and ranked.iloc[top_n - 1][key] == ranked.iloc[top_n][key]:
        last = ranked.iloc[top_n - 1]
        tied = ranked[ranked[key] == last[key]]
        names = ", ".join(f"{r['name']} ({int(r['negative'])} of {int(r['conversations'])})" for _, r in tied.iterrows())
        tie_rule = "higher negative rate" if rank_by == "count" else "more negative conversations"
        unc.insert(0, f"Rank {top_n} is a tie: {names} share the same {'count' if rank_by == 'count' else 'rate'}. "
                      f"The tie-breaker ({tie_rule}) lists {last['name']}; the others are equally entitled to the last place.")
    count_top = set(by_count.head(top_n)["name"])
    rate_top = set(by_rate.head(top_n)["name"])
    if count_top != rate_top:
        unc.append("The top list changes if ranked by negative rate instead of count: "
                   f"by rate the top {top_n} would include {', '.join(sorted(rate_top - count_top))} instead of {', '.join(sorted(count_top - rate_top))}.")
    small = df[df["conversations"] < min_conversations]
    if len(small):
        unc.append(f"{len(small)} {dimension} group(s) have fewer than {min_conversations} conversations; their rates are unstable.")
    if dimension == "topic" and "general_help" in set(top["key"]):
        notes.append("'General help request' merges the English and Hinglish help-request templates, so it has roughly twice the volume of other topics; "
                     "its opening message is neutral, which lowers its negative rate.")
    unc.append("Sentiment and topic labels are derived from message templates by a deterministic rule set (see EVALUATION.md for agreement checks).")

    evidence: list[str] = []
    for _, r in top.head(3).iterrows():
        evidence += representative_conversations(db, scope, "topic" if dimension == "topic" else DIMENSIONS[dimension],
                                                 r["key"] if dimension == "topic" else r["name"], k=2)
    cols = ["rank", "name", "key", "negative", "conversations", "negative_rate", "rate_ci_low", "rate_ci_high", "share_of_negative", "escalation_requests", "rank_by_rate"]
    return AnalysisResult(
        operation="rank_negative_topics",
        params={"top_n": top_n, "dimension": dimension, "rank_by": rank_by, "min_conversations": min_conversations},
        scope=scope,
        metrics=[
            Metric(id="conversations_in_scope", label="Conversations in scope", value=total, unit="count"),
            Metric(id="negative_conversations", label="Negative conversations", value=total_neg, unit="count"),
            Metric(id="negative_rate_overall", label="Overall negative rate", value=round(total_neg / total, 4) if total else None, unit="percent",
                   numerator=total_neg, denominator=total),
            Metric(id="top_topic", label=f"Top {dimension}", value=str(top.iloc[0]["name"]), unit=None),
            Metric(id="top_topic_negative", label=f"Negative conversations in top {dimension}", value=int(top.iloc[0]["negative"]), unit="count",
                   numerator=int(top.iloc[0]["negative"]), denominator=total_neg),
            Metric(id="chi_square_p", label="Chi-square p (rate differs by group)", value=chi["p_value"], unit="p"),
        ],
        table=Table(columns=cols, rows=_rows(top[cols].round(4))),
        series={"all_groups": Table(columns=cols + ["mixed", "positive", "neutral", "mean_sentiment"],
                                    rows=_rows(ranked[cols + ["mixed", "positive", "neutral", "mean_sentiment"]].round(4)))},
        evidence_refs=evidence,
        method_notes=notes,
        uncertainty_notes=unc,
        coverage={"conversations": total, "groups": len(df)},
    )


def topic_frequency(db: AnalyticsDB, scope: Scope, dimension: str = "topic") -> AnalysisResult:
    df = topic_sentiment_table(db, scope, dimension)
    if df.empty:
        return AnalysisResult(operation="topic_frequency", scope=scope, status="insufficient_data", uncertainty_notes=["No conversations in scope."])
    total = int(df["conversations"].sum())
    df = df.sort_values(["conversations", "name"], ascending=[False, True]).reset_index(drop=True)
    df["share"] = df["conversations"] / total
    df["rank"] = range(1, len(df) + 1)
    cols = ["rank", "name", "key", "conversations", "share", "negative", "negative_rate"]
    return AnalysisResult(
        operation="topic_frequency", params={"dimension": dimension}, scope=scope,
        metrics=[Metric(id="conversations_in_scope", label="Conversations in scope", value=total, unit="count"),
                 Metric(id="groups", label=f"Distinct {dimension}s", value=len(df), unit="count"),
                 Metric(id="most_common", label=f"Most common {dimension}", value=str(df.iloc[0]["name"]))],
        table=Table(columns=cols, rows=_rows(df[cols].round(4))),
        method_notes=[COUNTING_RULE],
        coverage={"conversations": total},
    )


def compare_topics(db: AnalyticsDB, scope: Scope, topics: list[str]) -> AnalysisResult:
    if len(topics) < 2:
        return AnalysisResult(operation="compare_topics", scope=scope, status="insufficient_data",
                              uncertainty_notes=["Comparison needs at least two topics."])
    s = scope.model_copy(update={"topics": topics})
    df = topic_sentiment_table(db, s, "topic")
    if len(df) < 2:
        return AnalysisResult(operation="compare_topics", scope=s, status="insufficient_data",
                              uncertainty_notes=["Fewer than two of the requested topics have conversations in scope."])
    df = df.sort_values("negative_rate", ascending=False).reset_index(drop=True)
    w, p = where(s)
    extra = db.query(
        f"""SELECT topic AS key, AVG(empathy_response_rate) AS empathy_response_rate,
                   AVG(CASE WHEN resolution_relevant IS NULL THEN NULL ELSE resolution_relevant::INT END) AS resolution_relevance,
                   AVG(ends_negative::INT) AS ends_negative_rate, AVG(urgency_signals) AS urgency_per_conversation
            FROM conversations c WHERE {w} GROUP BY topic""", p)
    df = df.merge(extra, on="key", how="left")
    a, b = df.iloc[0], df.iloc[1]
    test = two_proportion_test(int(a["negative"]), int(a["conversations"]), int(b["negative"]), int(b["conversations"]))
    unc = []
    if test["p_value"] is not None:
        verdict = "is not statistically significant" if test["p_value"] >= 0.05 else "is statistically significant"
        unc.append(f"The difference in negative rate between {a['name']} and {b['name']} {verdict} (two-proportion z-test p = {test['p_value']}).")
    cols = ["name", "key", "conversations", "negative", "negative_rate", "rate_ci_low", "rate_ci_high", "mean_sentiment",
            "escalation_requests", "empathy_response_rate", "resolution_relevance", "ends_negative_rate", "urgency_per_conversation"]
    evidence = []
    for _, r in df.head(2).iterrows():
        evidence += representative_conversations(db, s, "topic", r["key"], k=2)
    return AnalysisResult(
        operation="compare_topics", params={"topics": topics}, scope=s,
        metrics=[Metric(id="difference_p", label="Difference p-value", value=test["p_value"], unit="p"),
                 Metric(id="rate_gap", label="Negative-rate gap", value=round(float(a["negative_rate"] - b["negative_rate"]), 4), unit="percent")],
        table=Table(columns=cols, rows=_rows(df[cols].round(4))),
        evidence_refs=evidence,
        method_notes=[COUNTING_RULE, NEGATIVE_RULE],
        uncertainty_notes=unc,
        coverage={"conversations": int(df["conversations"].sum())},
    )
