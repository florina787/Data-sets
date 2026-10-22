"""Query-driven dynamic dashboards.

Every question produces its own dashboard. The layout is chosen deterministically
from the analysis category and the charts the planner built from verified results;
nothing is added that the analysis did not compute. Each section states why its
charts were chosen. Refinements are follow-up questions the session memory already
supports (change window, filter to a group, drill into evidence), so clicking one
re-runs the analysis rather than re-filtering a client-side copy.
"""

from __future__ import annotations

from app.labeling.taxonomy import TOPICS

# chart_id -> (section, why this chart)
RATIONALE: dict[str, tuple[str, str]] = {
    "negative_topics": ("Answer", "A ranking question: horizontal bars order the groups by negative conversations."),
    "negative_rate_ci": ("Reliability", "Highest count is not highest rate; 95% intervals show which differences could be noise."),
    "priority_matrix": ("Answer", "Volume vs negativity: concerns in the top-right deserve review first."),
    "priority_scores": ("Answer", "Shows what drives each priority score, so the ranking is auditable."),
    "sensitivity": ("Reliability", "Does the ranking survive changes to the weights?"),
    "sentiment_trajectory": ("Answer", "A single conversation over time: a line of customer sentiment by turn."),
    "trajectory_timeline": ("Drill-down", "The annotated transcript behind the line."),
    "coaching_heatmap": ("Answer", "Agents × signals: where communication signals concentrate."),
    "empathy_distribution": ("Context", "How the selected agents compare with everyone else."),
    "sample_size": ("Reliability", "Conversations per agent: small samples are flagged, not ranked."),
    "coaching_by_topic": ("Context", "Whether the signal depends on the issue mix an agent handles."),
    "compare_topics": ("Answer", "Side-by-side comparison of the selected topics."),
    "topic_frequency": ("Answer", "How often each group occurs."),
    "sentiment_by_group": ("Context", "Sentiment mix per group."),
    "sentiment_distribution": ("Answer", "Overall sentiment mix."),
    "sentiment_trend": ("Context", "Month-by-month negative rate with intervals: is it changing?"),
    "resolution_misfit": ("Context", "Whether agents' closing actions fit the issue raised."),
    "root_cause_factors": ("Answer", "Candidate drivers: negative rate with vs without each factor."),
    "root_cause_ci": ("Reliability", "Interval for each factor's negative rate: overlap with the baseline means weak evidence."),
    "root_cause_alternatives": ("Reliability", "Alternative explanations that were checked before naming a driver."),
    "conversations_by_month": ("Context", "Coverage over time."),
    "retrieval_results": ("Evidence", "Semantically similar passages (hybrid MiniLM + LSA retrieval)."),
    "list_conversations": ("Drill-down", "The conversations behind the numbers."),
    "agent_profile": ("Drill-down", "This agent's conversations."),
    "conversation_detail": ("Drill-down", "The full transcript."),
}
SECTION_ORDER = ["Answer", "Reliability", "Context", "Evidence", "Drill-down"]
TITLES = {
    "negative_topics": "Negative sentiment by {dim}", "leadership_priorities": "Leadership priorities", "agent_coaching": "Coaching review",
    "sentiment_trajectory": "Conversation journey", "conversation_xray": "Conversation X-Ray", "root_cause": "Root cause investigation",
    "sentiment_trend": "Sentiment trend", "sentiment_distribution": "Sentiment mix", "topic_frequency": "Contact drivers",
    "compare_topics": "Topic comparison", "resolution_quality": "Resolution fit", "dataset_overview": "Dataset overview",
}


def _refinements(category: str, scope: dict, tool_results: dict) -> list[dict]:
    out: list[dict] = []
    window = scope.get("window", {})
    if window.get("rule") != "all":
        out.append({"label": "All dates", "question": "Same analysis across the whole dataset."})
        out.append({"label": "Previous month", "question": "What about the previous month?"})
    else:
        out.append({"label": "Latest month", "question": "Same analysis for the last month only."})
    rank = tool_results.get("rank_negative_topics") or tool_results.get("leadership_priorities")
    if rank and rank.get("table") and rank["table"]["rows"]:
        first = rank["table"]["rows"][0]
        if first.get("key") in TOPICS:
            out.append({"label": f"Why {first['name']}?", "question": f"What is driving negative sentiment in {first['name'].lower()}?"})
        out.append({"label": "Compare top two", "question": "Compare the top two topics."})
        out.append({"label": "Show examples", "question": "Show supporting examples for the first one."})
    if category == "root_cause":
        out.append({"label": "Coaching view", "question": "Which support agents may benefit from additional coaching on empathy?"})
    cid = (tool_results.get("conversation_xray") or tool_results.get("sentiment_trajectory") or {}).get("params", {}).get("conversation_id")
    if cid:
        out.append({"label": "Similar conversations", "question": f"Find conversations similar to {cid}."})
    return out[:5]


def build_dashboard(category: str, plan: dict, tool_results: dict, charts: list[dict], question: str) -> dict | None:
    content = [c for c in charts if c["chart_type"] != "kpi"]
    if not content and not any(c["chart_type"] == "kpi" for c in charts):
        return None
    sections: dict[str, list[dict]] = {}
    for c in content:
        sec, why = RATIONALE.get(c["chart_id"], ("Context", c.get("description") or ""))
        sections.setdefault(sec, []).append({"chart_id": c["chart_id"], "why": why,
                                             "width": "full" if c["chart_type"] in ("timeline", "table", "heatmap") else "half"})
    scope = plan.get("scope", {})
    filters = [{"field": "window", "value": scope.get("window", {}).get("label", "All dates")}]
    for f in ("topics", "products", "domains", "agents", "sentiments"):
        if scope.get(f):
            filters.append({"field": f, "value": ", ".join(TOPICS[v].label if f == "topics" and v in TOPICS else v for v in scope[f])})
    title = TITLES.get(category, category.replace("_", " ").capitalize())
    if "{dim}" in title:
        dim = (tool_results.get("rank_negative_topics") or {}).get("params", {}).get("dimension", "topic")
        title = title.format(dim=dim)
    return {
        "title": title,
        "generated_from": question,
        "kpi_chart_ids": [c["chart_id"] for c in charts if c["chart_type"] == "kpi"],
        "sections": [{"title": s, "items": sections[s]} for s in SECTION_ORDER if s in sections],
        "filters": filters,
        "refinements": _refinements(category, scope, tool_results),
        "operations": [s["op"] for s in plan.get("steps", [])],
        "layout_rule": "Layout chosen from the analysis type; every chart is copied from a verified result.",
    }
