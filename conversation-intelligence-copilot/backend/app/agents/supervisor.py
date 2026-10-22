"""Supervisor / analytical planner.

Turns a typed intent into an approved plan: a scope (dataset mode, resolved date
window, filters), at most MAX_STEPS registered operations, the specialist agent
that runs them, and whether/when retrieval runs. Follow-up references are
resolved against *deterministic* references stored in session memory and
re-validated against the database. The supervisor never computes numbers.
"""

from __future__ import annotations

import re

from app.analytics.db import get_db
from app.analytics.time_windows import resolve_window
from app.config import get_settings
from app.labeling.taxonomy import TOPICS
from app.llm.structured_output import IntentOutput
from app.schemas.analysis import Scope

MAX_STEPS = 4
MAX_RETRIEVAL_K = 10
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}

SPECIALIST = {
    "negative_topics": "topic_agent", "topic_frequency": "topic_agent", "compare_topics": "topic_agent",
    "sentiment_distribution": "sentiment_agent", "sentiment_trend": "sentiment_agent", "sentiment_trajectory": "sentiment_agent",
    "agent_coaching": "coaching_agent", "agent_profile": "coaching_agent",
    "leadership_priorities": "leadership_agent", "resolution_quality": "leadership_agent",
    "dataset_overview": "analytics_agent", "conversation_detail": "analytics_agent", "conversation_list": "analytics_agent",
    "explain_previous": "analytics_agent", "conversation_xray": "sentiment_agent", "root_cause": "leadership_agent", "uncertainty_review": "analytics_agent", "leadership_summary": "analytics_agent",
}
UNSUPPORTED_HELP = ("I can analyse sentiment, topics, products, agents' observable communication, conversation trajectories, "
                    "resolution fit and recurring concerns in the supplied conversations. The dataset has no revenue, cost, churn, "
                    "CSAT/NPS, handle-time or demographic fields, and I do not make personnel decisions.")


def _k_from_question(q: str, default: int = 5) -> int:
    m = re.search(r"\b(\d+|" + "|".join(NUM_WORDS) + r")\s+(supporting\s+)?(examples?|conversations?|cases?|excerpts?)", q.lower())
    if not m:
        return default
    v = m.group(1)
    return min(MAX_RETRIEVAL_K, int(v) if v.isdigit() else NUM_WORDS[v])


def _validate_ids(ids: list[str], column: str) -> tuple[list[str], list[str]]:
    if not ids:
        return [], []
    db = get_db()
    found = set(db.query(f"SELECT DISTINCT {column} FROM conversations WHERE {column} IN ({','.join('?' * len(ids))})", ids)[column])
    return [i for i in ids if i in found], [i for i in ids if i not in found]


def build_plan(intent: IntentOutput, previous: dict | None, dataset_mode: str, selected_conversation_id: str | None, question: str) -> dict:
    settings = get_settings()
    notes: list[str] = []
    resolved: dict = {}
    category = intent.category
    prev_refs = (previous or {}).get("refs", {})
    prev_scope = (previous or {}).get("scope", {})
    prev_plan = (previous or {}).get("plan", {})
    follow = intent.is_follow_up and previous is not None

    # --- dataset authorisation ---------------------------------------------
    if dataset_mode != "original" and not settings.enable_synthetic_demo:
        notes.append(f"Dataset mode '{dataset_mode}' is disabled (ENABLE_SYNTHETIC_DEMO=false); using the original dataset.")
        dataset_mode = "original"

    # --- date window -------------------------------------------------------
    spec = intent.time_window.model_dump(exclude_none=True)
    if spec.get("type") == "inherit":
        spec = prev_plan.get("window_spec", {"type": "all"}) if follow else {"type": "all"}
        if follow and spec.get("type") != "all":
            notes.append(f"Kept the previous date window ({prev_scope.get('window', {}).get('label', 'n/a')}).")
    elif spec.get("type") in ("previous_month", "next_month"):
        start = prev_scope.get("window", {}).get("start") if previous else None
        if start:
            spec["month"] = start[:7]
        else:
            spec = {"type": "previous_month"}  # relative to the latest month in the data
    window = resolve_window(get_db(), dataset_mode, spec)

    # --- filters (explicit > referenced > inherited) ------------------------------
    topics = list(intent.topics)
    products = list(intent.products)
    domains: list[str] = []
    ranking = prev_refs.get("ranking", [])
    if intent.reference_ranks and ranking:
        chosen = [r for r in ranking if r["rank"] in intent.reference_ranks]
        dim = prev_refs.get("dimension", "topic")
        keys = [r["key"] for r in chosen]
        if dim == "topic":
            topics = keys
        elif dim == "product":
            products = keys
        else:
            domains = keys
        resolved["references"] = [{"rank": r["rank"], "name": r["name"]} for r in chosen]
        if prev_refs.get("ranking_from"):
            notes.append("The previous answer had no ranking, so references use the most recent ranking in this session.")
        notes.append("Resolved '" + ", ".join(f"#{r['rank']}" for r in chosen) + "' from the previous answer: " + ", ".join(r["name"] for r in chosen) + ".")
    elif intent.reference_ranks and not ranking:
        notes.append("The question refers to an earlier ranking, but this session has no ranking to refer to.")
    sentiments = list(intent.sentiments)
    if follow:
        topics = topics or prev_scope.get("topics", [])
        products = products or prev_scope.get("products", [])
        domains = domains or prev_scope.get("domains", [])
        if not sentiments and category == prev_plan.get("category"):
            sentiments = prev_scope.get("sentiments", [])
    topics = [t for t in topics if t in TOPICS]
    agents, unknown_agents = _validate_ids(intent.agents, "agent_id")
    if unknown_agents:
        notes.append(f"Unknown agent ID(s) ignored: {', '.join(unknown_agents)}.")

    conv_ids, unknown_convs = _validate_ids(intent.conversation_ids, "conversation_id")
    if unknown_convs:
        notes.append(f"Conversation ID(s) not found: {', '.join(unknown_convs)}.")
    conversation_id = conv_ids[0] if conv_ids else None
    if not conversation_id and category in ("sentiment_trajectory", "conversation_detail", "conversation_xray"):
        if selected_conversation_id:
            ok, _ = _validate_ids([selected_conversation_id], "conversation_id")
            conversation_id = ok[0] if ok else None
            if conversation_id:
                notes.append(f"Using the conversation selected in the workspace ({conversation_id}).")
        elif previous and prev_refs.get("conversation_ids"):
            conversation_id = prev_refs["conversation_ids"][0]
            notes.append(f"Using conversation {conversation_id} from the previous answer.")

    scope = Scope(dataset_mode=dataset_mode, window=window, topics=topics, products=products, domains=domains, agents=agents,
                  sentiments=sentiments)
    top_n = intent.top_n or 5
    steps: list[dict] = []
    retrieval = {"mode": "none", "query": None, "k": 5, "scope": None}
    audience = intent.audience
    unsupported_reason = None

    def step(op: str, purpose: str, **params) -> None:
        steps.append({"op": op, "params": params, "purpose": purpose})

    if category == "negative_topics":
        step("rank_negative_topics", "Rank groups by negative conversations", top_n=top_n, dimension=intent.dimension, rank_by=intent.rank_by)
        step("sentiment_distribution", "Sentiment mix by group for context", group_by=intent.dimension)
        step("sentiment_trend", "Monthly trend for context")
        if intent.needs_evidence:
            retrieval = {"mode": "after_analysis", "query": None, "k": 3, "scope": None}
    elif category == "topic_frequency":
        step("topic_frequency", "Count conversations per group", dimension=intent.dimension)
    elif category == "compare_topics":
        step("compare_topics", "Compare the selected topics", topics=topics[:6])
        if len(topics) < 2:
            notes.append("Fewer than two topics named; the topic agent will compare the top two negative topics in scope.")
    elif category == "sentiment_distribution":
        step("sentiment_distribution", "Sentiment mix", group_by=intent.group_by)
    elif category == "sentiment_trend":
        step("sentiment_trend", "Monthly negative-sentiment trend")
    elif category == "sentiment_trajectory":
        step("sentiment_trajectory", "Turn-by-turn customer sentiment", conversation_id=conversation_id)
        if conversation_id:
            step("conversation_xray", "X-Ray of the same conversation (signals linked to messages)", conversation_id=conversation_id)
    elif category == "conversation_xray":
        if conversation_id:
            step("conversation_xray", "Message-level X-Ray: escalation, repeated concerns, communication gaps", conversation_id=conversation_id)
            step("sentiment_trajectory", "Turn-by-turn customer sentiment", conversation_id=conversation_id)
        else:
            step("sentiment_trajectory", "Suggest conversations to X-Ray", conversation_id=None)
    elif category == "root_cause":
        step("root_cause_investigation", "Test candidate drivers of negative sentiment", topic=topics[0] if topics else None)
        retrieval = {"mode": "after_analysis", "query": None, "k": 3, "scope": None}
    elif category == "agent_coaching":
        step("agent_coaching_review", "Communication review signals", min_conversations=settings.min_agent_conversations)
        retrieval = {"mode": "parallel", "query": "customer still not fixed asks to escalate urgent; agent asks for details without acknowledging frustration",
                     "k": 4, "scope": scope.model_copy(update={"sentiments": ["negative"]}).model_dump()}
    elif category == "agent_profile":
        if agents:
            step("agent_profile", "One agent's communication signals", agent_id=agents[0])
        else:
            unsupported_reason = "No valid agent ID was found in the question."
    elif category == "leadership_priorities":
        step("leadership_priorities", "Priority score for recurring concerns", top_n=top_n)
        step("sentiment_trend", "Trend context")
        step("resolution_quality", "Resolution fit context")
        retrieval = {"mode": "after_analysis", "query": None, "k": 3, "scope": None}
    elif category == "resolution_quality":
        step("resolution_quality", "Closing action vs issue")
    elif category == "dataset_overview":
        step("dataset_overview", "Coverage and labelling status")
    elif category == "conversation_detail":
        if conversation_id:
            step("conversation_detail", "Full transcript", conversation_id=conversation_id)
        else:
            unsupported_reason = "No conversation was selected or found."
    elif category == "conversation_list":
        order = "most_positive" if sentiments == ["positive"] else "most_negative"
        step("list_conversations", "Matching conversations", limit=25, order=order)
    elif category == "similar_conversations":
        k = _k_from_question(question)
        query = intent.search_query or question
        if follow and topics:
            query = " ".join(TOPICS[t].description for t in topics)
        retrieval = {"mode": "only", "query": query, "k": k, "scope": scope.model_dump()}
    elif category in ("explain_previous", "uncertainty_review", "leadership_summary"):
        if prev_plan.get("steps"):
            steps = prev_plan["steps"][:MAX_STEPS]
            scope = Scope(**prev_scope)
            resolved["rerun_of"] = previous.get("request_id")
            notes.append("Re-ran the previous analysis to answer from current data rather than from the earlier wording.")
            if category == "leadership_summary":
                audience = "leadership"
        elif category == "leadership_summary":
            audience = "leadership"
            step("leadership_priorities", "Priority score for recurring concerns", top_n=top_n)
        else:
            unsupported_reason = "There is no earlier analysis in this session to explain. Ask an analytical question first."
    elif category == "unsupported":
        unsupported_reason = intent.reasoning if intent.reasoning and "Rule-based" not in intent.reasoning else UNSUPPORTED_HELP
    specialist = SPECIALIST.get(category) if steps else None
    if category == "explain_previous" and steps:
        specialist = "analytics_agent"
    return {
        "category": category,
        "audience": audience,
        "specialist": specialist,
        "steps": steps[:MAX_STEPS],
        "retrieval": retrieval,
        "window_spec": spec,
        "scope": scope.model_dump(),
        "notes": notes,
        "resolved_references": resolved,
        "unsupported_reason": unsupported_reason,
        "limits": {"max_steps": MAX_STEPS, "max_retrieval_k": MAX_RETRIEVAL_K},
    }


def ranking_refs(tool_results: dict) -> dict:
    """Deterministic references stored in memory for follow-ups."""
    refs: dict = {"ranking": [], "conversation_ids": [], "dimension": "topic"}
    for op in ("leadership_priorities", "rank_negative_topics", "topic_frequency", "compare_topics"):
        r = tool_results.get(op)
        if r and r.get("table"):
            rows = r["table"]["rows"]
            refs["dimension"] = r.get("params", {}).get("dimension", "topic")
            refs["ranking"] = [{"rank": int(row.get("rank", i + 1)), "key": row.get("key") or row.get("name"), "name": row.get("name")}
                               for i, row in enumerate(rows)]
            refs["source_operation"] = op
            break
    for r in tool_results.values():
        refs["conversation_ids"] += [e for e in r.get("evidence_refs", []) if re.fullmatch(r"C\d{7}", e)]
        if r.get("operation") in ("sentiment_trajectory", "conversation_detail") and r.get("params", {}).get("conversation_id"):
            refs["conversation_ids"].insert(0, r["params"]["conversation_id"])
    refs["conversation_ids"] = list(dict.fromkeys(refs["conversation_ids"]))[:10]
    return refs

