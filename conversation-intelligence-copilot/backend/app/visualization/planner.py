"""Visualization planner: deterministic chart selection from verified results.

Chart choice follows the shape of the result (ranking -> horizontal bar, rate with
uncertainty -> error bars, time -> line, single conversation -> timeline,
prioritisation -> priority matrix, co-occurrence -> graph). Every data point is
copied from an AnalysisResult table; nothing is computed or invented here.
"""

from __future__ import annotations

from app.labeling.taxonomy import TOPICS
from app.visualization.schemas import ChartSpec, Drilldown, GraphEdge, GraphNode, GraphSpec, Series

SENTIMENT_COLORS = {"negative": "negative", "mixed": "mixed", "neutral": "neutral", "positive": "positive", "uncertain": "muted"}


def _kpis(result: dict, ids: list[str], rid: str) -> ChartSpec:
    rows = [m for m in result["metrics"] if m["id"] in ids]
    return ChartSpec(chart_id=f"{rid}_kpis", chart_type="kpi", title="Key figures", data=rows, source_analysis_id=rid,
                     dataset_scope=result["scope"]["dataset_mode"],
                     accessibility_summary="; ".join(f"{m['label']}: {m['value']}" for m in rows))


def _note(result: dict) -> str | None:
    return result["uncertainty_notes"][0] if result.get("uncertainty_notes") else None


def plan_charts(tool_results: dict, retrieval: list[dict], request_id: str) -> tuple[list[ChartSpec], list[GraphSpec]]:
    charts: list[ChartSpec] = []
    graphs: list[GraphSpec] = []
    rid = request_id

    if (r := tool_results.get("rank_negative_topics")) and r["status"] == "ok":
        dim = r["params"]["dimension"]
        drill = Drilldown(kind="topic" if dim == "topic" else "product", field="key" if dim == "topic" else "name")
        charts.append(_kpis(r, ["conversations_in_scope", "negative_conversations", "negative_rate_overall", "top_topic"], f"{rid}_neg"))
        rows = r["table"]["rows"]
        charts.append(ChartSpec(
            chart_id="negative_topics", chart_type="horizontal_bar", title=f"Top negative {dim}s · {r['scope']['window']['label']}",
            description="Ranked by number of negative conversations", x_field="name",
            series=[Series(key="negative", label="Negative conversations", color="negative"),
                    Series(key="conversations", label="All conversations", color="muted")],
            data=[{k: row[k] for k in ("name", "key", "negative", "conversations", "negative_rate")} for row in rows],
            filters=r["scope"], source_analysis_id=rid, evidence_ids=r["evidence_refs"], uncertainty_note=_note(r), drilldown=drill,
            accessibility_summary="; ".join(f"{row['name']}: {int(row['negative'])} negative of {int(row['conversations'])}" for row in rows)))
        allg = r["series"]["all_groups"]["rows"]
        charts.append(ChartSpec(
            chart_id="negative_rate_ci", chart_type="error_bar", title="Negative rate with 95% confidence interval",
            description="Highest count is not the same as highest rate; overlapping intervals mean the difference may be noise.",
            x_field="name", y_field="negative_rate", series=[Series(key="negative_rate", label="Negative rate", color="violet")],
            data=[{k: row[k] for k in ("name", "key", "negative_rate", "rate_ci_low", "rate_ci_high", "conversations")} for row in
                  sorted(allg, key=lambda x: -x["negative_rate"])],
            value_format="percent", error_low_field="rate_ci_low", error_high_field="rate_ci_high", source_analysis_id=rid, drilldown=drill,
            accessibility_summary="; ".join(f"{row['name']}: {row['negative_rate']:.1%}" for row in allg)))
    if (r := tool_results.get("sentiment_distribution")) and r["status"] == "ok":
        if r["series"].get("by_group"):
            rows = r["series"]["by_group"]["rows"]
            charts.append(ChartSpec(
                chart_id="sentiment_by_group", chart_type="stacked_bar", title=f"Sentiment mix by {r['params']['group_by']}",
                x_field="name", series=[Series(key=s, label=s.capitalize(), color=SENTIMENT_COLORS[s]) for s in ("negative", "mixed", "neutral", "positive")],
                data=[{k: row[k] for k in ("name", "negative", "mixed", "neutral", "positive", "total")} for row in rows],
                source_analysis_id=rid, uncertainty_note=_note(r),
                accessibility_summary="; ".join(f"{row['name']}: {int(row['negative'])} negative of {int(row['total'])}" for row in rows)))
        rows = r["table"]["rows"]
        charts.append(ChartSpec(
            chart_id="sentiment_distribution", chart_type="donut", title="Conversation sentiment", x_field="sentiment",
            series=[Series(key="conversations", label="Conversations")],
            data=[{"sentiment": row["sentiment"], "conversations": row["conversations"], "share": row["share"],
                   "color": SENTIMENT_COLORS.get(row["sentiment"], "muted")} for row in rows],
            source_analysis_id=rid, accessibility_summary="; ".join(f"{row['sentiment']}: {row['share']:.1%}" for row in rows)))
    if (r := tool_results.get("sentiment_trend")) and r["status"] == "ok":
        rows = r["table"]["rows"]
        charts.append(ChartSpec(
            chart_id="sentiment_trend", chart_type="line", title="Negative rate by month", x_field="month", y_field="negative_rate",
            series=[Series(key="negative_rate", label="Negative rate", color="cyan")],
            data=[{k: row[k] for k in ("month", "negative_rate", "rate_ci_low", "rate_ci_high", "conversations", "negative")} for row in rows],
            value_format="percent", error_low_field="rate_ci_low", error_high_field="rate_ci_high", source_analysis_id=rid,
            uncertainty_note=_note(r), drilldown=Drilldown(kind="month", field="month"),
            accessibility_summary="; ".join(f"{row['month']}: {row['negative_rate']:.1%}" for row in rows)))
    if (r := tool_results.get("topic_frequency")) and r["status"] == "ok":
        rows = r["table"]["rows"]
        charts.append(ChartSpec(
            chart_id="topic_frequency", chart_type="horizontal_bar", title=f"Conversations by {r['params']['dimension']}", x_field="name",
            series=[Series(key="conversations", label="Conversations", color="indigo")],
            data=[{k: row[k] for k in ("name", "key", "conversations", "share", "negative_rate")} for row in rows[:20]],
            source_analysis_id=rid, drilldown=Drilldown(kind="topic", field="key") if r["params"]["dimension"] == "topic" else None,
            accessibility_summary="; ".join(f"{row['name']}: {int(row['conversations'])}" for row in rows[:20])))
    if (r := tool_results.get("compare_topics")) and r["status"] == "ok":
        rows = r["table"]["rows"]
        metrics = [("negative_rate", "Negative rate"), ("ends_negative_rate", "Ends unresolved"), ("empathy_response_rate", "Empathic replies"),
                   ("resolution_relevance", "Closing action fits")]
        data = [{"metric": label, **{row["name"]: (row.get(k) if row.get(k) is not None else 0) for row in rows}} for k, label in metrics]
        colors = ["indigo", "cyan", "violet", "warning", "positive", "muted"]
        charts.append(ChartSpec(
            chart_id="compare_topics", chart_type="bar", title="Topic comparison", x_field="metric",
            series=[Series(key=row["name"], label=row["name"], color=colors[i % len(colors)]) for i, row in enumerate(rows)],
            data=data, value_format="percent", source_analysis_id=rid, uncertainty_note=_note(r), evidence_ids=r["evidence_refs"],
            accessibility_summary="; ".join(f"{row['name']}: negative {row['negative_rate']:.1%}" for row in rows)))
    if (r := tool_results.get("agent_coaching_review")) and r["status"] == "ok":
        charts.append(_kpis(r, ["agents_in_scope", "eligible_agents", "empathy_response_rate", "irrelevant_resolution_rate"], f"{rid}_coach"))
        heat = r["series"]["signal_heatmap"]["rows"]
        charts.append(ChartSpec(
            chart_id="coaching_heatmap", chart_type="heatmap", title="Review signals for flagged conversations",
            description="1 = signal present / worst. Rows are conversations (agent in brackets).",
            x_field="signal", y_field="conversation_id",
            data=[{"row": f"{h['conversation_id']} ({h['agent_id']})", "conversation_id": h["conversation_id"],
                   "cells": {"Missed empathy": h["missed_empathy_rate"], "Resolution misfit": h["irrelevant_resolution"],
                             "Ends unresolved": h["ends_negative"], "Escalation requests": min(1.0, (h["escalation_requests"] or 0) / 3)}} for h in heat],
            source_analysis_id=rid, evidence_ids=[h["conversation_id"] for h in heat], drilldown=Drilldown(kind="conversation", field="conversation_id"),
            accessibility_summary=f"{len(heat)} conversations flagged for review."))
        dist = r["series"]["empathy_distribution"]["rows"]
        charts.append(ChartSpec(
            chart_id="empathy_distribution", chart_type="bar", title="Share of negative turns answered with empathy (per conversation)",
            x_field="bucket", series=[Series(key="conversations", label="Conversations", color="violet")], data=dist, source_analysis_id=rid,
            accessibility_summary="; ".join(f"{d['bucket']}: {d['conversations']}" for d in dist)))
        bt = r["series"]["by_topic"]["rows"]
        charts.append(ChartSpec(
            chart_id="coaching_by_topic", chart_type="bar", title="Communication signals by topic", x_field="topic_label",
            series=[Series(key="empathy_response_rate", label="Empathic replies", color="positive"),
                    Series(key="irrelevant_resolution_rate", label="Resolution misfit", color="warning")],
            data=[{k: (row[k] if row[k] is not None else 0) for k in ("topic_label", "empathy_response_rate", "irrelevant_resolution_rate")} for row in bt],
            value_format="percent", source_analysis_id=rid,
            accessibility_summary="; ".join(f"{row['topic_label']}: empathy {row['empathy_response_rate'] or 0:.0%}" for row in bt)))
        ss = r["series"]["sample_size"]["rows"]
        charts.append(ChartSpec(
            chart_id="sample_size", chart_type="bar", title="Conversations per agent (sample size)", x_field="conversations_per_agent",
            series=[Series(key="agents", label="Agents", color="muted")], data=ss, source_analysis_id=rid, uncertainty_note=_note(r),
            accessibility_summary="; ".join(f"{d['conversations_per_agent']} conversation(s): {d['agents']} agents" for d in ss)))
    if (r := tool_results.get("sentiment_trajectory")) and r.get("series", {}).get("trajectory"):
        charts.append(_kpis(r, ["customer_turns", "first_followup_score", "final_score", "net_change", "turning_points"], f"{rid}_traj"))
        traj = r["series"]["trajectory"]["rows"]
        tps = {t["turn_index"]: t for t in r["series"]["turning_points"]["rows"]}
        charts.append(ChartSpec(
            chart_id="sentiment_trajectory", chart_type="line", title=f"Customer sentiment · {r['params']['conversation_id']}",
            description="Each point is a customer message in turn order; markers are turning points.", x_field="turn_index",
            series=[Series(key="sentiment_score", label="Message sentiment", color="cyan"), Series(key="rolling_mean", label="Running mean", color="violet")],
            data=[{"turn_index": t["turn_index"], "sentiment_score": t["sentiment_score"], "rolling_mean": t["rolling_mean"], "label": t["act"],
                   "text": t["text"], "message_id": t["message_id"], "turning_point": tps.get(t["turn_index"], {}).get("direction")} for t in traj],
            value_format="score", source_analysis_id=rid, evidence_ids=r["evidence_refs"], drilldown=Drilldown(kind="message", field="message_id"),
            accessibility_summary="; ".join(f"turn {t['turn_index']}: {t['sentiment_score']:+.1f}" for t in traj)))
        charts.append(ChartSpec(
            chart_id="trajectory_timeline", chart_type="timeline", title="Annotated transcript timeline",
            data=r["table"]["rows"], source_analysis_id=rid, evidence_ids=r["evidence_refs"],
            accessibility_summary=f"{len(r['table']['rows'])} messages in turn order."))
    if (r := tool_results.get("leadership_priorities")) and r["status"] == "ok":
        charts.append(_kpis(r, ["conversations_in_scope", "concerns", "top_concern", "top_score", "unresolved_rate_overall", "top1_stability"], f"{rid}_lead"))
        pm = r["series"]["priority_matrix"]["rows"]
        charts.append(ChartSpec(
            chart_id="priority_matrix", chart_type="priority_matrix", title="Priority matrix: volume vs negative rate",
            description="Bubble size = priority score. Top-right = high volume and high negativity.", x_field="conversations", y_field="negative_rate",
            data=pm, source_analysis_id=rid, drilldown=Drilldown(kind="topic", field="key"), uncertainty_note=_note(r),
            accessibility_summary="; ".join(f"{p['name']}: {int(p['conversations'])} conversations, {p['negative_rate']:.1%} negative, score {p['priority_score']}" for p in pm)))
        rows = r["table"]["rows"]
        weights = r["params"]["weights"]
        labels = {w["signal"]: w["label"] for w in r["series"]["weights"]["rows"]}
        palette = ["indigo", "negative", "warning", "violet", "cyan", "muted"]
        charts.append(ChartSpec(
            chart_id="priority_scores", chart_type="stacked_bar", title="Priority score and what drives it", x_field="name",
            series=[Series(key=f"contrib_{k}", label=labels[k], color=palette[i % len(palette)]) for i, k in enumerate(weights)],
            data=[{"name": row["name"], "key": row["key"], "priority_score": row["priority_score"], **{f"contrib_{k}": row[f"contrib_{k}"] for k in weights}} for row in rows],
            value_format="score", source_analysis_id=rid, drilldown=Drilldown(kind="topic", field="key"),
            accessibility_summary="; ".join(f"{row['name']}: {row['priority_score']}" for row in rows)))
        sens = r["series"]["sensitivity"]["rows"]
        charts.append(ChartSpec(chart_id="sensitivity", chart_type="table", title="Sensitivity of the ranking to weight changes",
                                data=sens, source_analysis_id=rid, accessibility_summary=f"{len(sens)} weight scenarios tested."))
    if (r := tool_results.get("resolution_quality")) and r["status"] == "ok":
        rows = [x for x in r["table"]["rows"] if x.get("misfit_rate") is not None]
        charts.append(ChartSpec(
            chart_id="resolution_misfit", chart_type="horizontal_bar", title="Closing action does not fit the issue", x_field="topic_label",
            series=[Series(key="misfit_rate", label="Misfit rate", color="warning")],
            data=[{"topic_label": x["topic_label"], "misfit_rate": x["misfit_rate"], "conversations": x["conversations"]} for x in rows],
            value_format="percent", source_analysis_id=rid, uncertainty_note=_note(r),
            accessibility_summary="; ".join(f"{x['topic_label']}: {x['misfit_rate']:.0%}" for x in rows)))
        matrix = r["series"]["matrix"]["rows"]
        nodes = {}
        edges = []
        for m in matrix:
            a = f"issue:{m['topic_label']}"
            b = f"res:{m['final_resolution']}"
            nodes[a] = GraphNode(id=a, label=m["topic_label"], kind="issue")
            nodes[b] = GraphNode(id=b, label=m["final_resolution"].replace("_", " "), kind="resolution")
            edges.append(GraphEdge(source=a, target=b, weight=m["conversations"], label=str(m["conversations"]),
                                   relation="observed"))
        graphs.append(GraphSpec(graph_id="issue_resolution_graph", title="Issue → agent closing action",
                                description="Edges are observed counts of conversations with that issue ending in that action.",
                                nodes=list(nodes.values()), edges=edges, source_analysis_id=rid))
    if (r := tool_results.get("dataset_overview")) and r["status"] == "ok":
        charts.append(_kpis(r, ["conversations_in_scope", "messages", "agents", "topics", "products", "label_coverage"], f"{rid}_ds"))
        charts.append(ChartSpec(chart_id="conversations_by_month", chart_type="bar", title="Conversations by start month", x_field="month",
                                series=[Series(key="conversations", label="Conversations", color="indigo")], data=r["table"]["rows"],
                                source_analysis_id=rid, accessibility_summary="; ".join(f"{x['month']}: {x['conversations']}" for x in r["table"]["rows"])))
    for op in ("list_conversations", "agent_profile", "conversation_detail"):
        if (r := tool_results.get(op)) and r.get("table") and r["table"]["rows"]:
            charts.append(ChartSpec(chart_id=op, chart_type="table", title={"list_conversations": "Matching conversations",
                                    "agent_profile": "Agent's conversations", "conversation_detail": "Transcript"}[op],
                                    data=r["table"]["rows"], source_analysis_id=rid, evidence_ids=r["evidence_refs"],
                                    drilldown=Drilldown(kind="conversation", field="conversation_id") if op != "conversation_detail" else None,
                                    accessibility_summary=f"{len(r['table']['rows'])} rows."))
    if retrieval:
        charts.append(ChartSpec(
            chart_id="retrieval_results", chart_type="horizontal_bar", title="Retrieved passages by similarity", x_field="conversation_id",
            series=[Series(key="similarity", label="Cosine similarity", color="cyan")],
            data=[{"conversation_id": x["conversation_id"], "similarity": x["similarity"], "topic": x["topic"]} for x in retrieval],
            value_format="number", source_analysis_id=rid, evidence_ids=[x["evidence_id"] for x in retrieval],
            drilldown=Drilldown(kind="conversation", field="conversation_id"),
            uncertainty_note="Similarity is a ranking signal between embeddings, not a probability or confidence.",
            accessibility_summary="; ".join(f"{x['conversation_id']}: {x['similarity']:.2f}" for x in retrieval)))
    return charts, graphs


def topic_label(key: str) -> str:
    return TOPICS[key].label if key in TOPICS else key
