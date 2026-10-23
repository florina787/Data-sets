"""Deterministic, evidence-grounded narratives built only from verified results.

This is the explanation of record when no model is used, and the baseline a
model explanation is checked against. Every number here comes from an
AnalysisResult produced by a registered operation.
"""

from __future__ import annotations

RESOLUTION_LABELS = {"service_activated": "service activated", "escalated": "escalated to specialists", "out_for_delivery": "out for delivery",
                     "refund_issued": "refund issued", "coupon_applied": "coupon applied", "account_reset": "account reset"}


def pct(x, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def _m(result: dict, metric_id: str, default=None):
    return next((m["value"] for m in result.get("metrics", []) if m["id"] == metric_id), default)


def _window(result: dict) -> str:
    label = result.get("scope", {}).get("window", {}).get("label", "All dates")
    return "all dates" if label == "All dates" else label


def negative_topics(r: dict, extra: dict) -> dict:
    rows = r["table"]["rows"]
    dim = r["params"].get("dimension", "topic")
    total, neg = _m(r, "conversations_in_scope"), _m(r, "negative_conversations")
    listing = ", ".join(f"{row['name']} ({int(row['negative'])})" for row in rows)
    by_rate = sorted(r["series"]["all_groups"]["rows"], key=lambda x: (-x["negative_rate"], x["name"]))
    top_rate = next((x for x in by_rate if x["conversations"] >= r["params"].get("min_conversations", 20)), by_rate[0])
    first = rows[0]
    answer = (f"{neg} of {total} conversations in {_window(r)} were negative ({pct(_m(r, 'negative_rate_overall'))}). "
              f"Ranked by number of negative conversations, the top {len(rows)} {dim}s are {listing}. "
              f"{first['name']} accounts for {pct(first['share_of_negative'])} of negative conversations. "
              f"By negative rate rather than count, {top_rate['name']} is highest at {pct(top_rate['negative_rate'])} "
              f"(95% CI {pct(top_rate['rate_ci_low'])}–{pct(top_rate['rate_ci_high'])}).")
    tie = next((n for n in r.get("uncertainty_notes", []) if n.startswith("Rank ") and "is a tie" in n), None)
    if tie:
        answer += " " + tie
    return {
        "headline": f"Top negative {dim}s in {_window(r)}: " + ", ".join(row["name"] for row in rows[:5]) + ".",
        "answer": answer,
        "key_points": [f"#{int(row['rank'])} {row['name']}: {int(row['negative'])} negative of {int(row['conversations'])} "
                       f"({pct(row['negative_rate'])}, 95% CI {pct(row['rate_ci_low'])}–{pct(row['rate_ci_high'])})" for row in rows],
        "follow_up_questions": ["Compare the top two topics.", "What about the previous month?", "Show three supporting examples.",
                                "Which agents handled those concerns?"],
    }


def topic_frequency(r: dict, extra: dict) -> dict:
    rows = r["table"]["rows"]
    dim = r["params"].get("dimension", "topic")
    return {
        "headline": f"The most common {dim} in {_window(r)} is {rows[0]['name']} ({int(rows[0]['conversations'])} conversations, {pct(rows[0]['share'])}).",
        "answer": f"{_m(r, 'conversations_in_scope')} conversations across {len(rows)} {dim}s. "
                  + "; ".join(f"{row['name']} {int(row['conversations'])} ({pct(row['share'])})" for row in rows[:6]) + ".",
        "key_points": [f"{row['name']}: {int(row['conversations'])} conversations, {pct(row['negative_rate'])} negative" for row in rows[:6]],
        "follow_up_questions": ["Which topics are most associated with negative sentiment?", "Show the sentiment trend over time."],
    }


def compare_topics(r: dict, extra: dict) -> dict:
    a, b = r["table"]["rows"][0], r["table"]["rows"][1]
    p = _m(r, "difference_p")
    sig = "a statistically significant difference" if p is not None and p < 0.05 else "a difference that is not statistically significant"
    return {
        "headline": f"{a['name']} is more often negative than {b['name']} ({pct(a['negative_rate'])} vs {pct(b['negative_rate'])}), {sig} (p = {p}).",
        "answer": f"In {_window(r)}, {a['name']} had {int(a['negative'])} negative of {int(a['conversations'])} conversations and "
                  f"{b['name']} had {int(b['negative'])} of {int(b['conversations'])}. Conversations ending unresolved: "
                  f"{pct(a['ends_negative_rate'])} vs {pct(b['ends_negative_rate'])}. Negative turns answered with empathy: "
                  f"{pct(a['empathy_response_rate'])} vs {pct(b['empathy_response_rate'])}.",
        "key_points": [f"{row['name']}: negative {pct(row['negative_rate'])}, escalation requests {int(row['escalation_requests'])}, "
                       f"closing action fits issue {pct(row['resolution_relevance'])}" for row in r["table"]["rows"]],
        "follow_up_questions": [f"Show similar conversations for {a['name']}.", "Which recurring concerns should leadership review first?"],
    }


def sentiment_distribution(r: dict, extra: dict) -> dict:
    rows = {row["sentiment"]: row for row in r["table"]["rows"]}
    parts = ", ".join(f"{k} {int(v['conversations'])} ({pct(v['share'])})" for k, v in rows.items())
    return {
        "headline": f"{pct(_m(r, 'negative_rate_overall'))} of conversations in {_window(r)} are negative.",
        "answer": f"Of {_m(r, 'conversations_in_scope')} conversations: {parts}. Most conversations are mixed because customers typically "
                  f"express both urgency or frustration and thanks within the same conversation.",
        "key_points": [f"{k.capitalize()}: {int(v['conversations'])} ({pct(v['share'])})" for k, v in rows.items()],
        "follow_up_questions": ["Break this down by topic.", "Show the sentiment trend over time.", "Show only negative conversations."],
    }


def sentiment_trend(r: dict, extra: dict) -> dict:
    rows = r["table"]["rows"]
    return {
        "headline": f"Negative sentiment was {pct(rows[0]['negative_rate'])} in {rows[0]['month']} and {pct(rows[-1]['negative_rate'])} in {rows[-1]['month']}.",
        "answer": "Monthly negative rate: " + "; ".join(f"{row['month']} {pct(row['negative_rate'])} of {int(row['conversations'])}" for row in rows) + ".",
        "key_points": [f"{row['month']}: {pct(row['negative_rate'])} (95% CI {pct(row['rate_ci_low'])}–{pct(row['rate_ci_high'])})" for row in rows],
        "follow_up_questions": ["Which topics drove negative sentiment last month?", "Compare the top two topics."],
    }


def sentiment_trajectory(r: dict, extra: dict) -> dict:
    if r["status"] == "insufficient_data" and not r.get("params", {}).get("conversation_id"):
        sugg = r["table"]["rows"] if r.get("table") else []
        return {
            "headline": "Select a conversation to trace its sentiment trajectory.",
            "answer": "No conversation was specified. " + (
                "These conversations have the largest customer sentiment swings and are good starting points: "
                + ", ".join(f"{s['conversation_id']} ({s['topic_label']}, {s['product']})" for s in sugg) + "." if sugg else ""),
            "key_points": [],
            "follow_up_questions": [f"How did sentiment change in {s['conversation_id']}?" for s in sugg[:3]],
        }
    cid = r["params"]["conversation_id"]
    tps = r["series"]["turning_points"]["rows"]
    first, final, net = _m(r, "first_followup_score"), _m(r, "final_score"), _m(r, "net_change")
    direction = "improved" if net > 0 else "worsened" if net < 0 else "ended where it started"
    tp_text = " ".join(
        f"At turn {t['turn_index']} sentiment {t['direction']} ({t['delta']:+.2f}): the customer wrote \"{t['customer_text']}\""
        + (f" after the agent said \"{t['preceding_agent_text']}\"." if t.get("preceding_agent_text") else ".") for t in tps[:3])
    return {
        "headline": f"In {cid} ({_m(r, 'topic')}), customer sentiment {direction}: {first:+.1f} at the first follow-up to {final:+.1f} at the end.",
        "answer": f"The customer opened with a {('negative' if _m(r, 'opening_score') < 0 else 'neutral')} issue report and sent "
                  f"{_m(r, 'customer_turns')} messages in total. {tp_text} Overall label: {_m(r, 'conversation_sentiment')}.",
        "key_points": [f"Turn {t['turn_index']}: {t['direction']} by {abs(t['delta']):.2f}" for t in tps] + [
            f"X-Ray [{x['severity']}]: {x['title']} — turns {', '.join(str(t) for t in x['turns'][:6])}"
            for x in (extra.get("conversation_xray") or {}).get("series", {}).get("signals", {}).get("rows", [])[:4]],
        "follow_up_questions": ["Show similar conversations.", "Did the agent's closing action fit the issue?", "Which agents may need coaching on empathy?"],
    }


def conversation_xray(r: dict, extra: dict) -> dict:
    cid = r["params"]["conversation_id"]
    sig = r["series"]["signals"]["rows"]
    high = [x for x in sig if x["severity"] == "high"]
    phases = {p["phase"]: p for p in r["series"]["phases"]["rows"]}
    arc = " → ".join(f"{p} {phases[p]['mean_sentiment']:+.2f}" for p in ("opening", "middle", "closing") if p in phases)
    lead = high[0] if high else (sig[0] if sig else None)
    answer = (f"{cid} ({_m(r, 'topic')}) has {_m(r, 'messages')} messages. The X-Ray found {_m(r, 'escalation_signals')} escalation signal(s), "
              f"{_m(r, 'repeated_concerns')} repeated concern(s) and {_m(r, 'communication_gaps')} communication gap(s); "
              f"{len(high)} are high severity. Mean customer sentiment by phase: {arc}.")
    if lead:
        answer += f" Most important: {lead['title'].lower()} (turn {', '.join(str(t) for t in lead['turns'][:4])}) — {lead['detail']}"
    return {
        "headline": f"X-Ray of {cid}: " + (f"{len(high)} high-severity finding(s), led by {lead['title'].lower()}." if high and lead
                                          else "no high-severity findings." if not high else ""),
        "answer": answer,
        "key_points": [f"[{x['severity']}] {x['title']} — turns {', '.join(str(t) for t in x['turns'][:6])}" for x in sig[:6]],
        "follow_up_questions": [f"How did customer sentiment change in {cid}?", "Show similar conversations.",
                                "Which agents may benefit from coaching on empathy?"],
    }


def root_cause(r: dict, extra: dict) -> dict:
    rows = r["table"]["rows"]
    topic = _m(r, "topic")
    drivers = [h for h in rows if h["role"] != "customer_reaction" and h["strength"] in ("strong association", "moderate association")]
    symptoms = [h for h in rows if h["role"] == "customer_reaction" and h["strength"] in ("strong association", "moderate association")]
    alts = r["series"]["alternatives"]["rows"]

    def line(h: dict) -> str:
        return (f"{h['description']}: {pct(h['negative_rate_with'], 0)} negative with it vs {pct(h['negative_rate_without'], 0)} without "
                f"(n={h['with_factor']} vs {h['without_factor']}, p={h['p_value']})")

    if drivers:
        top = drivers[0]
        headline = f"In {topic}, negative sentiment is most strongly associated with: {top['description'].split(' (')[0].lower()}."
        body = "Candidate drivers (association, not proof of cause): " + "; ".join(line(h) for h in drivers[:3]) + "."
        if top.get("precedes_negative_share") is not None:
            body += (f" In {pct(top['precedes_negative_share'], 0)} of the negative conversations with this behaviour it occurs before the "
                     "customer's last negative message, which is consistent with (but does not prove) it contributing.")
    else:
        headline = f"No agent or context factor is clearly associated with negative sentiment in {topic}."
        body = "None of the tested agent behaviours or context factors shows a reliable difference in negative rate."
    if symptoms:
        body += " Symptoms that accompany negativity rather than explain it: " + "; ".join(line(h) for h in symptoms[:2]) + "."
    return {
        "headline": headline,
        "answer": f"{_m(r, 'negative_conversations')} of {_m(r, 'conversations')} {topic} conversations in {_window(r)} were negative "
                  f"({pct(_m(r, 'negative_rate'))}). " + body,
        "key_points": [f"{a['alternative']}: {a['finding']}" for a in alts] + [
            f"{h['factor'].replace('_', ' ')} — {h['strength']}" for h in rows if h["role"] != "customer_reaction"][:4],
        "follow_up_questions": ["Which agents may benefit from coaching on empathy?", "Show supporting examples.",
                                "Does the agent's closing action fit the customer's issue, by topic?"],
    }


def agent_coaching(r: dict, extra: dict) -> dict:
    eligible = _m(r, "eligible_agents")
    queue = r["table"]["rows"]
    emp = next(m for m in r["metrics"] if m["id"] == "empathy_response_rate")
    mis = next(m for m in r["metrics"] if m["id"] == "irrelevant_resolution_rate")
    q_text = "; ".join(f"{q['conversation_id']} ({q['agent_id']}, {q['topic_label']}: {int(q['negative_turns_with_reply'])} negative customer turns, "
                       f"{int(q['empathic_replies'])} acknowledged)" for q in queue[:3])
    if eligible == 0:
        headline = (f"No agent has enough conversations for a fair individual comparison, so I've flagged conversations for review instead. "
                    f"Across the workforce, only {pct(emp['value'])} of negative customer turns got an acknowledgement or apology.")
    else:
        top = r["series"]["agents"]["rows"][:3]
        headline = "Agents to review first: " + ", ".join(f"{a['agent_id']} ({int(a['conversations'])} conversations)" for a in top) + "."
    return {
        "headline": headline,
        "answer": f"{emp['numerator']} of {emp['denominator']} negative customer turns were followed by an empathetic agent reply "
                  f"({pct(emp['value'])}), and {mis['numerator']} of {mis['denominator']} assessable closing actions did not fit the customer's issue "
                  f"({pct(mis['value'])}). Highest-priority conversations for a coaching review: {q_text}. "
                  "This is decision support: a team lead should read these transcripts before any coaching conversation.",
        "key_points": [f"{q['conversation_id']} · {q['agent_id']}: review score {q['review_score']}, closing action "
                       f"{RESOLUTION_LABELS.get(q['final_resolution'], q['final_resolution'])}" for q in queue[:5]],
        "follow_up_questions": [f"How did customer sentiment change in {queue[0]['conversation_id']}?" if queue else "Show the dataset overview.",
                                "Does the closing action fit the issue, by topic?", "Show similar conversations where the customer asked to escalate."],
    }


def agent_profile(r: dict, extra: dict) -> dict:
    a = r["params"]["agent_id"]
    return {
        "headline": f"{a} handled {_m(r, 'conversations')} conversation(s) in scope.",
        "answer": f"Negative customer turns answered with empathy: {pct(_m(r, 'empathy_response_rate'))}. Mean review score {_m(r, 'mean_review_score')}. "
                  "With this few conversations the signals describe individual transcripts, not the agent's overall style.",
        "key_points": [f"{row['conversation_id']}: {row['topic_label']}, review score {row['review_score']}" for row in r["table"]["rows"]],
        "follow_up_questions": ["Which agents may benefit from empathy coaching?"],
    }


def leadership(r: dict, extra: dict) -> dict:
    recs = r["series"]["recommendations"]["rows"]
    top = recs[0]
    return {
        "headline": f"Leadership should review {top['concern']} first (priority score {r['table']['rows'][0]['priority_score']}), then "
                    + ", ".join(x["concern"] for x in recs[1:3]) + ".",
        "answer": f"Across {_m(r, 'conversations_in_scope')} conversations ({_window(r)}), {r['table']['rows'][0]['name']} ranks first. "
                  f"{top['finding']} {top['rationale']} Suggested action: {top['suggested_action']} Owner: {top['decision_owner']}.",
        "key_points": [f"{x['priority']} · #{x['rank']} {x['concern']}: {x['suggested_action']}" for x in recs],
        "follow_up_questions": [f"Why was {top['concern']} ranked first?", "Compare the top two.", "Which findings are uncertain?",
                                "Summarize this for senior leadership."],
    }


def resolution_quality(r: dict, extra: dict) -> dict:
    m = next(x for x in r["metrics"] if x["id"] == "misfit_rate")
    rows = r["table"]["rows"]
    return {
        "headline": f"{pct(m['value'])} of assessable closing actions do not fit the customer's issue.",
        "answer": f"{m['numerator']} of {m['denominator']} conversations ended with an agent action unrelated to the issue raised "
                  f"(e.g. a refund for a locked account). Highest misfit: {rows[0]['topic_label']} ({pct(rows[0]['misfit_rate'])}).",
        "key_points": [f"{row['topic_label']}: misfit {pct(row['misfit_rate'])}" for row in rows if row.get("misfit_rate") is not None],
        "follow_up_questions": ["Which recurring concerns should leadership review first?"],
    }


def dataset_overview(r: dict, extra: dict) -> dict:
    return {
        "headline": f"{_m(r, 'conversations_in_scope')} conversations ({_m(r, 'messages')} messages), {_m(r, 'date_range')}.",
        "answer": f"{_m(r, 'agents')} agent IDs, {_m(r, 'topics')} issue topics and {_m(r, 'products')} products. "
                  f"{pct(_m(r, 'label_coverage'))} of conversations are fully labelled. " + " ".join(r.get("method_notes", [])),
        "key_points": [f"{row['month']}: {int(row['conversations'])} conversations" for row in r["table"]["rows"]],
        "follow_up_questions": ["What were the top 5 negative topics last month?", "Show the sentiment distribution."],
    }


def conversation_detail(r: dict, extra: dict) -> dict:
    cid = r["params"]["conversation_id"]
    return {
        "headline": f"{cid}: {_m(r, 'topic')} ({_m(r, 'product')}), handled by {_m(r, 'agent')}, overall {_m(r, 'sentiment')}.",
        "answer": f"{_m(r, 'messages')} messages. The agent's closing action was "
                  f"{RESOLUTION_LABELS.get(_m(r, 'final_resolution'), _m(r, 'final_resolution'))}; fits the issue: {_m(r, 'resolution_relevant')}.",
        "key_points": [],
        "follow_up_questions": [f"How did customer sentiment change in {cid}?", "Show similar conversations."],
    }


def conversation_list(r: dict, extra: dict) -> dict:
    rows = r["table"]["rows"]
    return {
        "headline": f"{_m(r, 'conversations_in_scope')} conversations match; showing the {len(rows)} most relevant.",
        "answer": "Most negative first: " + ", ".join(f"{x['conversation_id']} ({x['topic_label']}, {x['sentiment']})" for x in rows[:5]) + ".",
        "key_points": [],
        "follow_up_questions": [f"How did sentiment change in {rows[0]['conversation_id']}?" if rows else "Show the dataset overview."],
    }


def similar(results: list[dict], meta: dict) -> dict:
    if not results:
        return {"headline": "No matching passages were found.", "answer": meta.get("note") or "Try broader wording or fewer filters.",
                "key_points": [], "follow_up_questions": []}
    topics: dict[str, int] = {}
    for x in results:
        topics[x["topic"]] = topics.get(x["topic"], 0) + 1
    return {
        "headline": f"Found {len(results)} relevant conversations ({', '.join(f'{k}: {v}' for k, v in topics.items())}).",
        "answer": "Passages are ranked by cosine similarity between embeddings (a ranking signal, not a probability). "
                  + " ".join(f"{x['conversation_id']} (turns {x['turn_range'][0]}–{x['turn_range'][1]}, similarity {x['similarity']:.2f})." for x in results[:5]),
        "key_points": [f"{x['conversation_id']} · {x['topic']} · {x['product']} · {x['sentiment']}" for x in results],
        "follow_up_questions": [f"How did sentiment change in {results[0]['conversation_id']}?"],
    }


BY_OPERATION = {
    "rank_negative_topics": negative_topics, "topic_frequency": topic_frequency, "compare_topics": compare_topics,
    "sentiment_distribution": sentiment_distribution, "sentiment_trend": sentiment_trend, "sentiment_trajectory": sentiment_trajectory,
    "agent_coaching_review": agent_coaching, "agent_profile": agent_profile, "leadership_priorities": leadership,
    "resolution_quality": resolution_quality, "dataset_overview": dataset_overview, "conversation_detail": conversation_detail,
    "list_conversations": conversation_list, "conversation_xray": conversation_xray, "root_cause_investigation": root_cause,
}


def build(category: str, primary: dict | None, tool_results: dict, retrieval: list[dict], retrieval_meta: dict, plan: dict) -> dict:
    if plan.get("unsupported_reason"):
        return {"headline": "I can't answer that reliably from this dataset.", "answer": plan["unsupported_reason"], "key_points": [],
                "follow_up_questions": ["What were the top 5 topics most associated with negative sentiment last month?",
                                        "Which recurring customer concerns should leadership review first?"]}
    if category == "similar_conversations":
        return similar(retrieval, retrieval_meta)
    if primary is None:
        return {"headline": "The analysis could not be completed.", "answer": "No analytical result was produced. See the execution trace for details.",
                "key_points": [], "follow_up_questions": []}
    if primary["status"] == "insufficient_data" and primary["operation"] != "sentiment_trajectory":
        return {"headline": "Not enough data to answer this reliably.", "answer": " ".join(primary.get("uncertainty_notes", [])), "key_points": [],
                "follow_up_questions": ["Show the dataset overview."]}
    out = BY_OPERATION[primary["operation"]](primary, tool_results)
    if category == "uncertainty_review":
        notes = [n for r in tool_results.values() for n in r.get("uncertainty_notes", [])]
        out = {"headline": f"{len(notes)} caveats apply to the previous analysis.", "answer": " ".join(notes[:4]),
               "key_points": notes, "follow_up_questions": out["follow_up_questions"]}
    if category == "explain_previous":
        methods = [n for r in tool_results.values() for n in r.get("method_notes", [])]
        out = {**out, "headline": "How the previous result was calculated: " + out["headline"], "key_points": methods + out["key_points"]}
    return out
