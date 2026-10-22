"""Agent communication / empathy coaching signals.

This is decision support for a human reviewer, never a performance judgement.
Signals are observable behaviours in the transcript:

* missed empathy: after a negative customer turn, the next agent turn neither
  acknowledges the frustration nor apologises;
* irrelevant resolution: the agent's closing action does not plausibly address
  the customer's issue (mapping in taxonomy.RELEVANT_RESOLUTIONS);
* scripted repetition: the same agent sentence used more than once.

review_score (0-100) = 100 x mean of the available components
(missed-empathy rate, irrelevant-resolution flag). Higher = more worth reviewing.
"""

from __future__ import annotations

import pandas as pd

from app.analytics.db import AnalyticsDB, where
from app.analytics.stats import wilson_interval
from app.analytics.topics import _rows
from app.schemas.analysis import AnalysisResult, Metric, Scope, Table

SCORE_RULE = ("review_score = 100 × mean(missed-empathy rate after negative customer turns, irrelevant-resolution flag), "
              "using whichever components are observable in the conversation.")
SAFEGUARD = ("Decision support only: these signals describe a small number of transcripts and are not a performance assessment. "
             "A team lead should read the cited conversations before any coaching conversation.")


def _conversation_signals(db: AnalyticsDB, scope: Scope) -> pd.DataFrame:
    w, p = where(scope)
    df = db.query(
        f"""SELECT conversation_id, agent_id, topic, topic_label, product, sentiment, negative_turns_with_reply, empathic_replies,
                   empathy_response_rate, empathy_turns, agent_turns, empathy_rate, repeated_agent_phrases, final_resolution,
                   resolution_relevant, ends_negative, escalation_requests, opening_language, agent_hinglish_turns
            FROM conversations c WHERE {w} AND agent_id IS NOT NULL""", p)
    if df.empty:
        return df
    missed = 1 - pd.to_numeric(df["empathy_response_rate"], errors="coerce").astype("float64")
    # Float with NaN for "not assessable", even when no conversation in scope is assessable.
    irrelevant = df["resolution_relevant"].map(lambda v: float("nan") if v is None or pd.isna(v) else float(not v)).astype("float64")
    comps = pd.concat([missed, irrelevant], axis=1)
    df["missed_empathy_rate"] = missed
    df["irrelevant_resolution"] = irrelevant
    df["review_score"] = (comps.mean(axis=1, skipna=True) * 100).round(1)
    return df


def _agent_table(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("agent_id").agg(
        conversations=("conversation_id", "count"),
        negative_turns=("negative_turns_with_reply", "sum"),
        empathic_replies=("empathic_replies", "sum"),
        empathy_turns=("empathy_turns", "sum"),
        agent_turns=("agent_turns", "sum"),
        irrelevant_resolutions=("irrelevant_resolution", lambda s: int(s.fillna(0).sum())),
        assessable_resolutions=("irrelevant_resolution", lambda s: int(s.notna().sum())),
        ends_negative=("ends_negative", "sum"),
        mean_review_score=("review_score", "mean"),
    ).reset_index()
    g["empathy_response_rate"] = g["empathic_replies"] / g["negative_turns"].where(g["negative_turns"] > 0)
    g["empathy_rate"] = g["empathy_turns"] / g["agent_turns"]
    g["irrelevant_resolution_rate"] = g["irrelevant_resolutions"] / g["assessable_resolutions"].where(g["assessable_resolutions"] > 0)
    ci = [wilson_interval(int(e), int(n)) if n else (None, None) for e, n in zip(g["empathic_replies"], g["negative_turns"])]
    g["empathy_ci_low"], g["empathy_ci_high"] = [c[0] for c in ci], [c[1] for c in ci]
    return g


def agent_coaching_review(db: AnalyticsDB, scope: Scope, min_conversations: int = 3, top_n: int = 10) -> AnalysisResult:
    df = _conversation_signals(db, scope)
    if df.empty:
        return AnalysisResult(operation="agent_coaching_review", scope=scope, status="insufficient_data",
                              uncertainty_notes=["No conversations with agent identifiers in scope."])
    agents = _agent_table(df)
    eligible = agents[agents["conversations"] >= min_conversations].sort_values(["mean_review_score", "conversations"], ascending=[False, False])
    dist = agents["conversations"].value_counts().sort_index()
    total_neg = int(df["negative_turns_with_reply"].sum())
    total_emp = int(df["empathic_replies"].sum())
    assessable = df["irrelevant_resolution"].notna()
    irrelevant = int(df.loc[assessable, "irrelevant_resolution"].sum())

    queue = df.sort_values(["review_score", "negative_turns_with_reply", "conversation_id"], ascending=[False, False, True]).head(top_n)
    unc = [SAFEGUARD]
    if eligible.empty:
        unc.insert(0, f"No agent has {min_conversations} or more conversations in scope (max is {int(agents['conversations'].max())}; "
                      f"{int(dist.get(1, 0))} of {len(agents)} agents handled exactly one). Ranking individual agents would rest on one or two "
                      "transcripts, so this answer prioritises conversations for review and reports workforce-wide patterns instead.")
        ranked_agents = agents[agents["conversations"] >= 2].sort_values(["mean_review_score", "agent_id"], ascending=[False, True]).head(top_n)
        agent_note = "exploratory (2 conversations each; below the minimum sample size)"
    else:
        ranked_agents = eligible.head(top_n)
        agent_note = f"agents with at least {min_conversations} conversations"
    unc.append("Empathy is detected from fixed phrases ('I understand this is frustrating', 'I'm sorry about the trouble'); "
               "it measures observable acknowledgement, not how the customer felt.")
    if df["repeated_agent_phrases"].sum() == 0:
        unc.append("No agent repeated the same sentence within a conversation, so scripted repetition is not a differentiating signal in this dataset.")

    queue_cols = ["conversation_id", "agent_id", "topic_label", "negative_turns_with_reply", "empathic_replies", "missed_empathy_rate",
                  "final_resolution", "resolution_relevant", "ends_negative", "review_score"]
    agent_cols = ["agent_id", "conversations", "negative_turns", "empathic_replies", "empathy_response_rate", "empathy_ci_low", "empathy_ci_high",
                  "empathy_rate", "irrelevant_resolution_rate", "ends_negative", "mean_review_score"]
    heat_cols = ["conversation_id", "agent_id", "missed_empathy_rate", "irrelevant_resolution", "ends_negative", "escalation_requests"]
    heat = queue[heat_cols].copy()
    heat["ends_negative"] = heat["ends_negative"].astype(float)
    buckets = pd.cut(df["empathy_response_rate"].dropna(), bins=[-0.01, 0.0, 0.25, 0.5, 0.75, 1.0],
                     labels=["0%", "1–25%", "26–50%", "51–75%", "76–100%"]).value_counts().sort_index()
    by_topic = df.groupby("topic_label").agg(conversations=("conversation_id", "count"),
                                             empathy_response_rate=("empathy_response_rate", "mean"),
                                             irrelevant_resolution_rate=("irrelevant_resolution", "mean")).reset_index().sort_values("irrelevant_resolution_rate", ascending=False)
    return AnalysisResult(
        operation="agent_coaching_review",
        params={"min_conversations": min_conversations, "top_n": top_n},
        scope=scope,
        metrics=[
            Metric(id="agents_in_scope", label="Agents in scope", value=len(agents), unit="count"),
            Metric(id="eligible_agents", label=f"Agents with ≥{min_conversations} conversations", value=len(eligible), unit="count"),
            Metric(id="empathy_response_rate", label="Negative turns answered with empathy", value=round(total_emp / total_neg, 4) if total_neg else None,
                   unit="percent", numerator=total_emp, denominator=total_neg),
            Metric(id="irrelevant_resolution_rate", label="Closing action does not fit the issue", value=round(irrelevant / int(assessable.sum()), 4) if assessable.sum() else None,
                   unit="percent", numerator=irrelevant, denominator=int(assessable.sum())),
            Metric(id="conversations_reviewed", label="Conversations analysed", value=len(df), unit="count"),
        ],
        table=Table(columns=queue_cols, rows=_rows(queue[queue_cols].round(4))),
        series={
            "agents": Table(columns=agent_cols + ["note"], rows=[{**r, "note": agent_note} for r in _rows(ranked_agents[agent_cols].round(4))]),
            "signal_heatmap": Table(columns=heat_cols, rows=_rows(heat.round(4))),
            "empathy_distribution": Table(columns=["bucket", "conversations"], rows=[{"bucket": str(k), "conversations": int(v)} for k, v in buckets.items()]),
            "by_topic": Table(columns=["topic_label", "conversations", "empathy_response_rate", "irrelevant_resolution_rate"], rows=_rows(by_topic.round(4))),
            "sample_size": Table(columns=["conversations_per_agent", "agents"], rows=[{"conversations_per_agent": int(k), "agents": int(v)} for k, v in dist.items()]),
        },
        evidence_refs=queue["conversation_id"].head(5).tolist(),
        method_notes=[SCORE_RULE, "Missed empathy = share of negative customer turns whose next agent turn has no acknowledgement or apology.",
                      "Resolution fit uses a documented issue→action mapping (ASSUMPTIONS.md); general help requests are not assessable."],
        uncertainty_notes=unc,
        coverage={"conversations": len(df), "agents": len(agents), "min_conversations": min_conversations},
    )


def agent_profile(db: AnalyticsDB, scope: Scope, agent_id: str) -> AnalysisResult:
    s = scope.model_copy(update={"agents": [agent_id]})
    df = _conversation_signals(db, s)
    if df.empty:
        return AnalysisResult(operation="agent_profile", params={"agent_id": agent_id}, scope=s, status="insufficient_data",
                              uncertainty_notes=[f"No conversations found for agent {agent_id} in scope."])
    a = _agent_table(df).iloc[0]
    cols = ["conversation_id", "topic_label", "sentiment", "negative_turns_with_reply", "empathic_replies", "final_resolution", "resolution_relevant", "review_score"]
    unc = [SAFEGUARD]
    if len(df) < 3:
        unc.insert(0, f"Only {len(df)} conversation(s) for this agent: too few to characterise their communication style.")
    return AnalysisResult(
        operation="agent_profile", params={"agent_id": agent_id}, scope=s,
        metrics=[Metric(id="conversations", label="Conversations", value=int(a["conversations"]), unit="count"),
                 Metric(id="empathy_response_rate", label="Negative turns answered with empathy",
                        value=None if pd.isna(a["empathy_response_rate"]) else round(float(a["empathy_response_rate"]), 4), unit="percent",
                        numerator=int(a["empathic_replies"]), denominator=int(a["negative_turns"])),
                 Metric(id="mean_review_score", label="Mean review score", value=round(float(a["mean_review_score"]), 1), unit="score")],
        table=Table(columns=cols, rows=_rows(df[cols].round(4))),
        evidence_refs=df["conversation_id"].tolist()[:5],
        method_notes=[SCORE_RULE],
        uncertainty_notes=unc,
        coverage={"conversations": len(df)},
    )
