"""LangGraph node implementations. Each is wrapped by `traced` for real progress events."""

from __future__ import annotations

import json
import time

from app.agents import narrative
from app.agents.governance_agent import review as governance_review
from app.agents.grounding import allowed_numbers, ungrounded_numbers
from app.agents.intent_agent import resolve_intent
from app.agents.qa_agent import run_qa
from app.agents.supervisor import build_plan, ranking_refs
from app.agents.tracing import traced
from app.analytics.db import get_db
from app.analytics.query_registry import OperationError, run_operation
from app.config import get_settings
from app.governance.prompt_injection import MAX_QUESTION_CHARS, sanitize_question, scan
from app.labeling.taxonomy import TOPICS
from app.llm.gemini_client import LLMUnavailable, get_llm
from app.llm.structured_output import ExplanationOutput
from app.memory.store import get_memory
from app.prompts.registry import get_prompt
from app.retrieval.evidence import assemble
from app.retrieval.index import RetrievalUnavailable, get_retriever
from app.schemas.analysis import Scope
from app.visualization.planner import plan_charts

REQUEST_BUDGET_SECONDS = 90.0
RESPONSE_VERSION = "1.0"


class InvalidInput(ValueError):
    pass


# --- input & context -----------------------------------------------------------

@traced("input_validation", critical=True, summarize_output=lambda u: {"chars": len(u.get("user_question", "")), "flags": len(u.get("governance_findings", []))})
def input_validation(state: dict) -> dict:
    raw = state.get("user_question") or ""
    q = sanitize_question(raw)
    if not q:
        raise InvalidInput("The question is empty.")
    flags = scan(q)
    findings = [{"policy": "input_length", "outcome": "truncated", "detail": f"Question truncated to {MAX_QUESTION_CHARS} characters"}] if len(raw) > MAX_QUESTION_CHARS else []
    if flags:
        findings.append({"policy": "prompt_injection", "outcome": "flagged", "detail": f"{len(flags)} injection pattern(s) matched", "patterns": flags})
    return {"user_question": q, "governance_findings": findings, "started_at": state.get("started_at") or time.time()}


@traced("session_context", summarize_output=lambda u: {"history_turns": len(u.get("conversation_history", [])),
                                                         "has_previous": u.get("previous_turn") is not None})
def session_context(state: dict) -> dict:
    mem = get_memory()
    settings = get_settings()
    history = mem.history(state["session_id"], settings.max_history_turns)
    previous = mem.last_successful(state["session_id"])
    return {"conversation_history": [{"question": h["question"], "category": h["intent"].get("category"), "summary": h["summary"]} for h in history],
            "previous_turn": previous}


@traced("intent", summarize_input=lambda s: {"question": s.get("user_question", "")[:200]},
        summarize_output=lambda u: {"category": u["resolved_intent"]["category"], "source": u["intent_source"],
                                    "window": u["resolved_intent"]["time_window"], "follow_up": u["resolved_intent"]["is_follow_up"]})
def intent(state: dict) -> dict:
    hist = get_memory().history(state["session_id"], get_settings().max_history_turns)
    out, source, meta = resolve_intent(state["user_question"], state.get("previous_turn"), hist, state["request_id"])
    return {"resolved_intent": out.model_dump(), "intent_source": source, "_meta": meta}


@traced("supervisor", summarize_output=lambda u: {"steps": [s["op"] for s in u["analytical_plan"]["steps"]],
                                                    "specialist": u["analytical_plan"]["specialist"],
                                                    "retrieval": u["analytical_plan"]["retrieval"]["mode"],
                                                    "window": u["analytical_plan"]["scope"]["window"]["label"],
                                                    "notes": u["analytical_plan"]["notes"]})
def supervisor(state: dict) -> dict:
    from app.llm.structured_output import IntentOutput

    plan = build_plan(IntentOutput(**state["resolved_intent"]), state.get("previous_turn"), state.get("dataset_mode", "original"),
                      state.get("selected_conversation_id"), state["user_question"])
    return {"analytical_plan": plan, "dataset_scope": plan["scope"]}


# --- specialists ----------------------------------------------------------------------

def _run_steps(state: dict, post=None) -> dict:
    plan = state["analytical_plan"]
    scope = Scope(**plan["scope"])
    db = get_db()
    results: dict = {}
    errors: list[dict] = []
    for s in plan["steps"]:
        params = dict(s["params"])
        if s["op"] == "compare_topics" and len(params.get("topics", [])) < 2:
            # Dependency: compare the two most negative topics in scope.
            rank = results.get("rank_negative_topics") or run_operation(db, "rank_negative_topics", scope, {"top_n": 2}).model_dump()
            params["topics"] = [r["key"] for r in rank["table"]["rows"][:2]] if rank.get("table") else []
        try:
            results[s["op"]] = run_operation(db, s["op"], scope, params).model_dump()
        except OperationError as e:
            errors.append({"node": "specialist", "error": str(e)[:300]})
    if post:
        post(results)
    out = {"tool_results": results, "_meta": {"operations": list(results)}}
    if errors:
        out["errors"] = errors
    return out


def _spec_summary(u: dict) -> dict:
    return {op: {"status": r["status"], "metrics": {m["id"]: m["value"] for m in r["metrics"][:4]}} for op, r in u.get("tool_results", {}).items()}


topic_agent = traced("topic_agent", summarize_output=_spec_summary)(lambda s: _run_steps(s))
sentiment_agent = traced("sentiment_agent", summarize_output=_spec_summary)(lambda s: _run_steps(s))
coaching_agent = traced("coaching_agent", summarize_output=_spec_summary)(lambda s: _run_steps(s))
leadership_agent = traced("leadership_agent", summarize_output=_spec_summary)(lambda s: _run_steps(s))
analytics_agent = traced("analytics_agent", summarize_output=_spec_summary)(lambda s: _run_steps(s))


# --- retrieval ----------------------------------------------------------------------------

def _retrieval_request(state: dict) -> tuple[str | None, Scope, int]:
    plan = state["analytical_plan"]
    r = plan["retrieval"]
    scope = Scope(**(r.get("scope") or plan["scope"]))
    query = r.get("query")
    if r["mode"] == "after_analysis":
        tr = state.get("tool_results", {})
        src = tr.get("leadership_priorities") or tr.get("rank_negative_topics")
        if src and src.get("table") and src["table"]["rows"]:
            top = src["table"]["rows"][0]
            key = top.get("key")
            if key in TOPICS:
                scope = scope.model_copy(update={"topics": [key], "sentiments": ["negative"]})
                query = f"{TOPICS[key].description} Customer is frustrated, it is still not fixed and asks to escalate."
    return query, scope, min(int(r.get("k", 5)), plan["limits"]["max_retrieval_k"])


@traced("retrieval", summarize_input=lambda s: {"mode": s["analytical_plan"]["retrieval"]["mode"]},
        summarize_output=lambda u: {"results": len(u.get("retrieved_evidence", [])), **{k: v for k, v in u.get("retrieval_meta", {}).items()
                                                                                       if k in ("latency_ms", "embedding_backend", "query", "candidates")}})
def retrieval(state: dict) -> dict:
    query, scope, k = _retrieval_request(state)
    if not query:
        return {"retrieved_evidence": [], "retrieval_meta": {"note": "No retrieval query could be formed."}, "_status": "skipped"}
    try:
        out = get_retriever().search(query, scope, k=k)
    except RetrievalUnavailable as e:
        return {"retrieved_evidence": [], "retrieval_meta": {"note": str(e), "available": False}, "errors": [{"node": "retrieval", "error": str(e)}]}
    return {"retrieved_evidence": out["results"], "retrieval_meta": {**{k_: v for k_, v in out.items() if k_ != "results"}, "query": query[:200],
                                                                     "filters": {"topics": scope.topics, "sentiments": scope.sentiments,
                                                                                 "window": scope.window.label}}}


# --- evidence, explanation, visualisation -------------------------------------------------------

REASONS = {
    "rank_negative_topics": "Among the most negative conversations in a top-ranked group",
    "compare_topics": "Representative negative conversation for a compared topic",
    "agent_coaching_review": "Flagged for coaching review (highest review score)",
    "leadership_priorities": "Representative negative conversation for a top-priority concern",
    "sentiment_trajectory": "Turning point in the customer's sentiment",
    "list_conversations": "Matches the requested filters",
    "agent_profile": "Conversation handled by this agent",
    "conversation_detail": "Selected conversation",
}


@traced("evidence", summarize_output=lambda u: {"items": len(u.get("evidence", [])), "validation": u.get("_meta", {})})
def evidence(state: dict) -> dict:
    refs = [(ref, REASONS.get(op, "Cited by the analysis")) for op, r in state.get("tool_results", {}).items() for ref in r.get("evidence_refs", [])]
    items, report = assemble(get_db(), refs, state.get("retrieved_evidence", []), state["analytical_plan"]["scope"]["dataset_mode"])
    return {"evidence": items, "_meta": report, "verified_metrics": {"evidence_report": report}}


def _facts(tool_results: dict) -> dict:
    facts = {}
    for op, r in tool_results.items():
        facts[op] = {
            "window": r["scope"]["window"]["label"],
            "metrics": [{k: m[k] for k in ("id", "label", "value", "numerator", "denominator") if m.get(k) is not None} for m in r["metrics"]],
            "rows": (r.get("table") or {}).get("rows", [])[:12],
            "series": {k: v["rows"][:12] for k, v in r.get("series", {}).items()},
            "method": r.get("method_notes", []),
            "uncertainty": r.get("uncertainty_notes", []),
            "params": r.get("params", {}),
        }
    return facts


@traced("explanation", summarize_output=lambda u: {"source": u.get("explanation_source"), "headline": u.get("explanation", {}).get("headline", "")[:160]})
def explanation(state: dict) -> dict:
    plan = state["analytical_plan"]
    tool_results = state.get("tool_results", {})
    primary = tool_results.get(plan["steps"][0]["op"]) if plan.get("steps") and tool_results else None
    det = narrative.build(plan["category"], primary, tool_results, state.get("retrieved_evidence", []), state.get("retrieval_meta", {}), plan)
    facts = _facts(tool_results)
    facts["retrieval"] = [{k: x[k] for k in ("conversation_id", "similarity", "topic", "product", "turn_range")} for x in state.get("retrieved_evidence", [])]
    llm = get_llm()
    elapsed = time.time() - state.get("started_at", time.time())
    if plan.get("unsupported_reason") or not llm.available() or elapsed > REQUEST_BUDGET_SECONDS * 0.6:
        reason = "unsupported question" if plan.get("unsupported_reason") else "model unavailable" if not llm.available() else "time budget"
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {"facts": facts}, "_meta": {"reason": reason}}
    prompt = get_prompt("grounded_explanation")
    unc = [n for r in tool_results.values() for n in r.get("uncertainty_notes", [])][:6]
    ev = [{"conversation_id": e["conversation_id"], "excerpts": [x["text"] for x in e["excerpts"][:3]]} for e in state.get("evidence", [])[:4]]
    try:
        res = llm.generate_json(prompt, prompt.render(audience=plan.get("audience", "analyst"), question=state["user_question"],
                                                      facts=json.dumps(facts, default=str)[:12000], uncertainty=json.dumps(unc),
                                                      evidence=json.dumps(ev, ensure_ascii=False)[:3000]),
                                ExplanationOutput, request_id=state["request_id"], purpose="explanation")
    except LLMUnavailable as e:
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {"facts": facts}, "_meta": {"reason": str(e)[:200]}}
    out = res.parsed.model_dump()  # type: ignore[union-attr]
    text = " ".join([out["headline"], out["answer"], *out["key_points"]])
    bad = ungrounded_numbers(text, allowed_numbers(facts))
    if bad:
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {"facts": facts},
                "governance_findings": state.get("governance_findings", []) + [{"policy": "numeric_grounding", "outcome": "rejected_model_output",
                                                                                "detail": f"Gemini explanation contained ungrounded numbers {bad[:5]}; deterministic narrative used."}],
                "_meta": {"reason": "grounding check failed", "ungrounded": bad[:5], "tokens": res.usage.total_tokens}}
    out["key_points"] = out["key_points"] or det["key_points"]
    out["follow_up_questions"] = out["follow_up_questions"] or det["follow_up_questions"]
    return {"explanation": out, "explanation_source": "llm", "verified_metrics": {"facts": facts},
            "_meta": {"tokens": res.usage.total_tokens, "cache_hit": res.cache_hit, "retries": res.retries}}


@traced("visualization", summarize_output=lambda u: {"charts": [c["chart_id"] for c in u.get("visualizations", [])], "graphs": len(u.get("graphs", []))})
def visualization(state: dict) -> dict:
    charts, graphs = plan_charts(state.get("tool_results", {}), state.get("retrieved_evidence", []), state["request_id"])
    return {"visualizations": [c.model_dump() for c in charts], "graphs": [g.model_dump() for g in graphs]}


# --- verification & governance ---------------------------------------------------------------

@traced("qa", summarize_output=lambda u: {"status": u["qa_results"]["status"], "passed": f"{u['qa_results']['passed']}/{u['qa_results']['total']}"})
def qa(state: dict) -> dict:
    facts = state.get("verified_metrics", {}).get("facts", {})
    report = state.get("verified_metrics", {}).get("evidence_report", {})
    res = run_qa(state["analytical_plan"], state.get("tool_results", {}), state.get("visualizations", []), state.get("evidence", []),
                 report, state.get("explanation", {}), facts)
    return {"qa_results": res}


@traced("governance", summarize_output=lambda u: {"findings": [f"{f['policy']}:{f['outcome']}" for f in u.get("governance_findings", [])]})
def governance(state: dict) -> dict:
    flags = [p for f in state.get("governance_findings", []) for p in f.get("patterns", [])]
    unc = [n for r in state.get("tool_results", {}).values() for n in r.get("uncertainty_notes", [])]
    unc = list(dict.fromkeys(unc))
    expl, ev, unc, findings = governance_review(state["analytical_plan"], dict(state.get("explanation", {})), state.get("evidence", []), flags, unc)
    prior = [f for f in state.get("governance_findings", []) if f["policy"] in ("input_length", "numeric_grounding")]
    return {"explanation": expl, "evidence": ev, "uncertainty_notes": unc, "governance_findings": prior + findings}


# --- response & persistence ----------------------------------------------------------------------

def _model_metadata(state: dict) -> dict:
    llm = get_llm()
    st = llm.status()
    return {"provider": st.get("provider"), "model": st.get("model"), "mode": "llm" if state.get("intent_source") == "llm" or state.get("explanation_source") == "llm" else "deterministic",
            "available": st.get("available"), "reason": st.get("reason"), "intent_source": state.get("intent_source"),
            "explanation_source": state.get("explanation_source"), "label_source": get_settings().label_source,
            "embedding_backend": state.get("retrieval_meta", {}).get("embedding_backend")}


@traced("response", summarize_output=lambda u: {"status": u["final_response"]["status"], "charts": len(u["final_response"]["charts"])})
def response(state: dict) -> dict:
    from app.schemas.api_response import ChatResponse

    plan = state["analytical_plan"]
    tool_results = state.get("tool_results", {})
    expl = state.get("explanation", {})
    metrics = [m for r in tool_results.values() for m in r.get("metrics", []) if m.get("unit") != "p"][:12]
    rankings = []
    for op in ("leadership_priorities", "rank_negative_topics", "topic_frequency"):
        if op in tool_results and tool_results[op].get("table"):
            rankings = tool_results[op]["table"]["rows"]
            break
    recs = tool_results.get("leadership_priorities", {}).get("series", {}).get("recommendations", {}).get("rows", [])
    if not plan.get("steps") and plan["category"] != "similar_conversations":
        status = "unsupported" if plan.get("unsupported_reason") else "failed"
    elif any(r["status"] == "insufficient_data" for r in tool_results.values()):
        status = "insufficient_data"
    elif state.get("qa_results", {}).get("status") == "fail":
        status = "needs_review"
    else:
        status = "completed"
    resp = ChatResponse(
        version=RESPONSE_VERSION, request_id=state["request_id"], session_id=state["session_id"], status=status,
        question=state["user_question"], resolved_intent=state.get("resolved_intent", {}), dataset_scope=plan["scope"],
        plan={k: plan[k] for k in ("category", "specialist", "steps", "retrieval", "notes", "resolved_references", "audience")},
        headline=expl.get("headline", ""), answer=expl.get("answer", ""), key_points=expl.get("key_points", []),
        metrics=metrics, rankings=rankings, charts=state.get("visualizations", []), graphs=state.get("graphs", []),
        evidence=state.get("evidence", []), recommendations=recs, uncertainty_notes=state.get("uncertainty_notes", []),
        method_notes=list(dict.fromkeys(n for r in tool_results.values() for n in r.get("method_notes", []))),
        follow_up_questions=expl.get("follow_up_questions", []), execution_trace_id=state["request_id"],
        model_metadata=_model_metadata(state), quality_status=state.get("qa_results", {}),
        governance=state.get("governance_findings", []),
        human_review_required=any(f["policy"] == "human_review" for f in state.get("governance_findings", [])),
        errors=state.get("errors", []),
    )
    return {"final_response": resp.model_dump()}


@traced("memory_telemetry", summarize_output=lambda u: {"saved": True})
def memory_telemetry(state: dict) -> dict:
    fr = state["final_response"]
    refs = ranking_refs(state.get("tool_results", {}))
    for e in state.get("retrieved_evidence", []):
        if e["conversation_id"] not in refs["conversation_ids"]:
            refs["conversation_ids"].append(e["conversation_id"])
    plan = state["analytical_plan"]
    get_memory().add_turn(state["session_id"], state["request_id"], state["user_question"], state.get("resolved_intent", {}), plan["scope"],
                          {"category": plan["category"], "steps": plan["steps"], "window_spec": plan["window_spec"]}, refs,
                          fr["headline"], "completed" if fr["status"] in ("completed", "insufficient_data", "needs_review") else fr["status"])
    return {}
