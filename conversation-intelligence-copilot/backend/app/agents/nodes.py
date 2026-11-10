"""LangGraph node implementations. Each is wrapped by `traced` for real progress events."""

from __future__ import annotations

import json
import re
import time

from app.agents import narrative
from app.agents.evidence_challenger import challenge, claim_constraints
from app.agents.governance_agent import review as governance_review
from app.agents.grounding import allowed_numbers, ungrounded_numbers
from app.agents.groundedness import score as groundedness_score
from app.agents.suggestions import suggest
from app.agents.intent_agent import resolve_intent
from app.agents.intent_router import route_intent
from app.agents.router import decide as route_decision
from app.agents.qa_agent import run_qa
from app.agents.supervisor import build_plan, ranking_refs
from app.agents.tracing import _emit, traced
from app.analytics.db import get_db
from app.analytics.query_registry import OperationError, run_operation
from app.config import get_settings
from app.governance.prompt_injection import MAX_QUESTION_CHARS, sanitize_question, scan
from app.labeling.taxonomy import TOPICS
from app.llm.budget import model_budget
from app.llm.gemini_client import LLMUnavailable, get_llm
from app.llm.structured_output import ExplanationOutput
from app.memory.store import get_memory
from app.observability.store import get_telemetry
from app.prompts.registry import get_prompt
from app.retrieval.evidence import assemble
from app.retrieval.index import RetrievalUnavailable, get_retriever
from app.schemas.analysis import Scope
from app.visualization.dashboard import build_dashboard
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


@traced("router", summarize_output=lambda u: {"route": u["routing"]["route"], "requested": u["routing"]["requested_mode"],
                                                "reason": u["routing"]["reason"], "llm_steps": u["routing"]["llm_steps"]})
def router(state: dict) -> dict:
    llm = get_llm()
    det = route_intent(state["user_question"], state.get("previous_turn"), allow_llm=False,
                       selected_conversation_id=state.get("selected_conversation_id"))
    routing = route_decision(state["user_question"], state.get("analysis_mode") or "auto", det.intent, llm.available(), llm.status().get("reason"),
                             unresolved=det.method in ("clarify", "rules_weak", "off_topic"))
    routing["intent_precheck"] = {k: v for k, v in det.meta().items() if k in ("method", "reason", "rule", "label")}
    return {"routing": routing}


@traced("intent", summarize_input=lambda s: {"question": s.get("user_question", "")[:200]},
        summarize_output=lambda u: {"category": u["resolved_intent"]["category"], "source": u["intent_source"],
                                    "method": u["intent_routing"]["method"], "reason": u["intent_routing"]["reason"],
                                    "window": u["resolved_intent"]["time_window"], "follow_up": u["resolved_intent"]["is_follow_up"]})
def intent(state: dict) -> dict:
    hist = get_memory().history(state["session_id"], get_settings().max_history_turns)
    allow = "intent" in (state.get("routing") or {}).get("llm_steps", ["intent"])
    out, source, meta = resolve_intent(state["user_question"], state.get("previous_turn"), hist, state["request_id"], allow_llm=allow,
                                       selected_conversation_id=state.get("selected_conversation_id"))
    return {"resolved_intent": out.model_dump(), "intent_source": source, "intent_routing": meta["routing"], "_meta": meta}


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
    ops: list[dict] = []
    for s in plan["steps"]:
        params = dict(s["params"])
        t0 = time.perf_counter()
        if s["op"] == "compare_topics" and len(params.get("topics", [])) < 2:
            # Dependency: compare the two most negative topics in scope.
            rank = results.get("rank_negative_topics") or run_operation(db, "rank_negative_topics", scope, {"top_n": 2}).model_dump()
            params["topics"] = [r["key"] for r in rank["table"]["rows"][:2]] if rank.get("table") else []
        try:
            results[s["op"]] = run_operation(db, s["op"], scope, params).model_dump()
            r = results[s["op"]]
            ops.append({"op": s["op"], "engine": "duckdb", "params": params, "status": r["status"], "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "rows": len((r.get("table") or {}).get("rows") or []), "metrics": len(r["metrics"])})
        except OperationError as e:
            errors.append({"node": "specialist", "error": str(e)[:300]})
            ops.append({"op": s["op"], "engine": "duckdb", "params": params, "status": "rejected", "duration_ms": round((time.perf_counter() - t0) * 1000, 1),
                        "error": str(e)[:200]})
    if post:
        post(results)
    out = {"tool_results": results, "_meta": {"operations": ops}}
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
        rc = tr.get("root_cause_investigation")
        src = tr.get("leadership_priorities") or tr.get("rank_negative_topics")
        if rc and rc.get("status") == "ok" and rc["params"].get("topic") in TOPICS:
            key = rc["params"]["topic"]
            top = next((h for h in rc["table"]["rows"] if h["role"] != "customer_reaction"), None)
            scope = scope.model_copy(update={"topics": [key], "sentiments": ["negative"]})
            query = f"{TOPICS[key].description} {top['description'] if top else ''} Customer is frustrated and it is still not fixed."
        elif src and src.get("table") and src["table"]["rows"]:
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
    filters = {"topics": scope.topics, "sentiments": scope.sentiments, "window": scope.window.label}
    meta = {k_: v for k_, v in out.items() if k_ != "results"}
    return {"retrieved_evidence": out["results"], "retrieval_meta": {**meta, "query": query[:200], "filters": filters},
            "_meta": {"engine": "faiss", "k": k, "mode": meta.get("mode"), "methods": meta.get("methods"), "fusion": meta.get("fusion"),
                      "filters": filters, "returned": len(out["results"]), "latency_ms": meta.get("latency_ms")}}


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
    "conversation_xray": "High-severity X-Ray finding",
    "root_cause_investigation": "Negative conversation showing the strongest associated factor",
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


# Columns the explanation never needs: interval bounds, internal keys and codes, evidence ID lists (evidence is passed separately).
_PROMPT_SKIP = re.compile(r"(^|_)ci(_|$)|_low$|_high$|^key$|^role$|^factor$|precedence_checked|^evidence")
PROMPT_FACTS_MAX_CHARS = 3000


def _prompt_facts(tool_results: dict, primary_op: str | None) -> str:
    """Compact, always-valid JSON of what the explanation needs: headline metrics and the top rows of the main result.
    The full facts still go to QA and the numeric grounding check, so the model can only use numbers that were verified."""
    def row(r: dict) -> dict:
        return {k: round(v, 3) if isinstance(v, float) else v for k, v in r.items()
                if v is not None and not isinstance(v, (list, dict)) and not _PROMPT_SKIP.search(k)}

    ops = ([primary_op] if primary_op in tool_results else []) + [o for o in tool_results if o != primary_op]
    text = "{}"
    for n_ops, n_rows in ((2, 5), (2, 3), (1, 3), (1, 1)):
        facts: dict = {}
        for op in ops[:n_ops]:
            r = tool_results[op]
            facts[op] = {
                "window": r["scope"]["window"]["label"],
                "metrics": [{k: (round(m[k], 4) if isinstance(m[k], float) else m[k]) for k in ("label", "value", "numerator", "denominator")
                             if m.get(k) is not None} for m in r["metrics"][:8]],
                "top_rows": [row(x) for x in (r.get("table") or {}).get("rows", [])[:n_rows]],
            }
            recs = r.get("series", {}).get("recommendations", {}).get("rows", [])
            if recs:
                facts[op]["recommendations"] = [row(x) for x in recs[:min(3, n_rows)]]
        text = json.dumps(facts, separators=(",", ":"), default=str)
        if len(text) <= PROMPT_FACTS_MAX_CHARS:
            break
    return text


def _draft_writer(request_id: str):
    """Stream a readable preview of the explanation while the model writes it (throttled)."""
    last = [0.0]

    def write(text: str) -> None:
        now = time.perf_counter()
        if now - last[0] < 0.25:
            return
        last[0] = now
        preview = re.sub(r'"(headline|answer|key_points|follow_up_questions)"\s*:\s*', "", text)
        preview = re.sub(r'[{}\[\]"]+', " ", preview)
        _emit({"type": "explanation_draft", "request_id": request_id, "text": " ".join(preview.split())[-400:]})
    return write


GENERAL_LABEL = "Model's own answer, not from the dataset."


def _general_answer_allowed(state: dict) -> bool:
    """Questions no analysis can answer (off-topic, unclear, or about data the dataset lacks) may get a labelled
    general-knowledge answer. Personnel decisions, protected attributes and requests for secrets stay refusals."""
    from app.agents.intent_rules import ALWAYS_REFUSE

    return state["analytical_plan"]["category"] == "unsupported" and not ALWAYS_REFUSE.search(state["user_question"])


def _general_answer(state: dict, llm, det: dict, facts: dict) -> dict | None:
    from app.agents.supervisor import UNSUPPORTED_HELP

    prompt = get_prompt("general_answer")
    try:
        with model_budget(get_settings().explanation_timeout_seconds, _draft_writer(state["request_id"])):
            res = llm.generate_json(prompt, prompt.render(capabilities=UNSUPPORTED_HELP, question=state["user_question"]), ExplanationOutput,
                                    request_id=state["request_id"], purpose="general_answer")
    except LLMUnavailable:
        return None
    out = res.parsed.model_dump()  # type: ignore[union-attr]
    out["answer"] = f"{GENERAL_LABEL} {out['answer']}".strip()  # the label travels with the text, so API clients see it too
    out["follow_up_questions"] = det["follow_up_questions"]  # computed nudges: always answerable, unlike model suggestions
    return {"explanation": out, "explanation_source": "general_knowledge", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts},
            "_meta": {"reason": "no analysis answers this question; labelled general-knowledge answer", "tokens": res.usage.total_tokens,
                      "cache_hit": res.cache_hit}}


@traced("explanation", summarize_output=lambda u: {"source": u.get("explanation_source"), "headline": u.get("explanation", {}).get("headline", "")[:160]})
def explanation(state: dict) -> dict:
    plan = state["analytical_plan"]
    tool_results = state.get("tool_results", {})
    primary = tool_results.get(plan["steps"][0]["op"]) if plan.get("steps") and tool_results else None
    det = narrative.build(plan["category"], primary, tool_results, state.get("retrieved_evidence", []), state.get("retrieval_meta", {}), plan)
    if plan["category"] == "unsupported":
        # Nudge towards the closest questions the data can answer, given this question and the session's recent ones.
        det["follow_up_questions"] = suggest(state["user_question"], [h["question"] for h in state.get("conversation_history", [])])
    facts = _facts(tool_results)
    facts["retrieval"] = [{k: x[k] for k in ("conversation_id", "similarity", "topic", "product", "turn_range")} for x in state.get("retrieved_evidence", [])]
    llm = get_llm()
    elapsed = time.time() - state.get("started_at", time.time())
    routed_out = "explanation" not in (state.get("routing") or {}).get("llm_steps", ["explanation"])
    if plan.get("unsupported_reason") and _general_answer_allowed(state) and not routed_out and llm.available():
        general = _general_answer(state, llm, det, facts)
        if general:
            return general
    if plan.get("unsupported_reason") or routed_out or not llm.available() or elapsed > REQUEST_BUDGET_SECONDS * 0.6:
        reason = ("unsupported question" if plan.get("unsupported_reason") else "router: analytics only" if routed_out
                  else "model unavailable" if not llm.available() else "time budget")
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts}, "_meta": {"reason": reason}}
    # The Evidence Challenger reviews the compact results first; the writer only runs when there is something it may claim.
    constraints = claim_constraints(tool_results, state.get("evidence", []))
    if not constraints["ready"]:
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts},
                "_meta": {"reason": "evidence pre-check: results incomplete", "constraints": constraints}}
    prompt = get_prompt("grounded_explanation")
    unc = [n[:220] for r in tool_results.values() for n in r.get("uncertainty_notes", [])][:3]
    ev = [{"conversation_id": e["conversation_id"], "excerpts": [x["text"][:160] for x in e["excerpts"][:2]]} for e in state.get("evidence", [])[:3]]
    timeout = get_settings().explanation_timeout_seconds
    try:
        with model_budget(timeout, _draft_writer(state["request_id"])):
            res = llm.generate_json(prompt, prompt.render(audience=plan.get("audience", "analyst"), question=state["user_question"],
                                                          facts=_prompt_facts(tool_results, plan["steps"][0]["op"] if plan.get("steps") else None),
                                                          constraints=json.dumps({k: constraints[k] for k in ("may_name", "must_not_name", "rules")},
                                                                                 ensure_ascii=False),
                                                          uncertainty=json.dumps(unc, ensure_ascii=False), evidence=json.dumps(ev, ensure_ascii=False)),
                                    ExplanationOutput, request_id=state["request_id"], purpose="explanation")
    except LLMUnavailable as e:
        out = {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts},
               "_meta": {"reason": str(e)[:200], "perf": getattr(llm, "last_perf", {})}}
        if "budget" in str(e):  # over the latency budget: the evidence-backed narrative keeps every citation and governance check
            out["governance_findings"] = state.get("governance_findings", []) + [{
                "policy": "latency_budget", "outcome": "deterministic_fallback",
                "detail": f"The model explanation did not fit the {timeout:g}s budget ({str(e)[:160]}); the deterministic, evidence-backed narrative was used."}]
        return out
    out = res.parsed.model_dump()  # type: ignore[union-attr]
    text = " ".join([out["headline"], out["answer"], *out["key_points"]])
    bad = ungrounded_numbers(text, allowed_numbers(facts))
    if bad:
        return {"explanation": det, "explanation_source": "deterministic", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts},
                "governance_findings": state.get("governance_findings", []) + [{"policy": "numeric_grounding", "outcome": "rejected_model_output",
                                                                                "detail": f"Model explanation contained ungrounded numbers {bad[:5]}; deterministic narrative used."}],
                "_meta": {"reason": "grounding check failed", "ungrounded": bad[:5], "tokens": res.usage.total_tokens, "perf": getattr(llm, "last_perf", {})}}
    out["key_points"] = out["key_points"] or det["key_points"]
    out["follow_up_questions"] = out["follow_up_questions"] or det["follow_up_questions"]
    return {"explanation": out, "explanation_source": "llm", "verified_metrics": {**state.get("verified_metrics", {}), "facts": facts, "baseline": det},
            "_meta": {"tokens": res.usage.total_tokens, "cache_hit": res.cache_hit, "retries": res.retries, "perf": getattr(llm, "last_perf", {}),
                      "constraints": {k: constraints[k] for k in ("may_name", "must_not_name")}}}


@traced("visualization", summarize_output=lambda u: {"charts": [c["chart_id"] for c in u.get("visualizations", [])], "graphs": len(u.get("graphs", [])),
                                                      "dashboard_sections": [x["title"] for x in (u.get("dashboard") or {}).get("sections", [])]})
def visualization(state: dict) -> dict:
    charts, graphs = plan_charts(state.get("tool_results", {}), state.get("retrieved_evidence", []), state["request_id"])
    specs = [c.model_dump() for c in charts]
    plan = state["analytical_plan"]
    dash = build_dashboard(plan["category"], plan, state.get("tool_results", {}), specs, state["user_question"]) if not plan.get("unsupported_reason") else None
    return {"visualizations": specs, "graphs": [g.model_dump() for g in graphs], "dashboard": dash}


# --- verification & governance ---------------------------------------------------------------

@traced("qa", summarize_output=lambda u: {"status": u["qa_results"]["status"], "passed": f"{u['qa_results']['passed']}/{u['qa_results']['total']}",
                                          "evidence_verdict": u["evidence_review"]["verdict"], "challenges": len(u["evidence_review"]["challenges"])})
def qa(state: dict) -> dict:
    facts = state.get("verified_metrics", {}).get("facts", {})
    report = state.get("verified_metrics", {}).get("evidence_report", {})
    plan, tool_results = state["analytical_plan"], state.get("tool_results", {})
    source = state.get("explanation_source", "")
    if source == "general_knowledge":  # nothing to challenge against the data; keep the model's wording and its label
        review, _ = challenge(get_db(), plan, tool_results, state.get("evidence", []), {}, source)
        expl = state.get("explanation", {})
    else:
        review, expl = challenge(get_db(), plan, tool_results, state.get("evidence", []), state.get("explanation", {}), source)
    out: dict = {}
    if review["replaced_explanation"]:
        expl = state.get("verified_metrics", {}).get("baseline") or expl
        out["explanation_source"] = "deterministic"
        out["governance_findings"] = state.get("governance_findings", []) + [{
            "policy": "evidence_challenger", "outcome": "rejected_model_output",
            "detail": "Model explanation named factors the analysis does not support; deterministic narrative used."}]
    source = out.get("explanation_source", source)
    res = run_qa(plan, tool_results, state.get("visualizations", []), state.get("evidence", []), report, expl, facts, review, basis=source)
    return {**out, "qa_results": res, "evidence_review": review, "explanation": expl,
            "groundedness": groundedness_score(expl, source, facts, review, plan)}


@traced("governance", summarize_output=lambda u: {"findings": [f"{f['policy']}:{f['outcome']}" for f in u.get("governance_findings", [])]})
def governance(state: dict) -> dict:
    flags = [p for f in state.get("governance_findings", []) for p in f.get("patterns", [])]
    unc = [n for r in state.get("tool_results", {}).values() for n in r.get("uncertainty_notes", [])]
    unc = list(dict.fromkeys(unc + (state.get("evidence_review") or {}).get("added_notes", [])))
    expl, ev, unc, findings = governance_review(state["analytical_plan"], dict(state.get("explanation", {})), state.get("evidence", []), flags, unc)
    prior = [f for f in state.get("governance_findings", []) if f["policy"] in ("input_length", "numeric_grounding", "evidence_challenger")]
    return {"explanation": expl, "evidence": ev, "uncertainty_notes": unc, "governance_findings": prior + findings}


# --- response & persistence ----------------------------------------------------------------------

def _model_metadata(state: dict) -> dict:
    llm = get_llm()
    st = llm.status()
    return {"provider": st.get("provider"), "model": st.get("model"), "mode": "llm" if state.get("intent_source") == "llm" or state.get("explanation_source") in ("llm", "general_knowledge") else "deterministic",
            "available": st.get("available"), "reason": st.get("reason"), "intent_source": state.get("intent_source"),
            "explanation_source": state.get("explanation_source"), "label_source": get_settings().label_source,
            "embedding_backend": state.get("retrieval_meta", {}).get("embedding_backend"),
            "routing": state.get("routing"), "intent_routing": state.get("intent_routing"), "token_usage": get_telemetry().request_usage(state["request_id"])}


def _panel(r: dict | None) -> dict | None:
    """Pass a structured result through to the UI (X-Ray, root cause) when it was computed."""
    if not r or r.get("status") != "ok":
        return None
    return {k: r.get(k) for k in ("operation", "params", "metrics", "table", "series", "method_notes", "uncertainty_notes", "coverage")}


@traced("response", summarize_output=lambda u: {"status": u["final_response"]["status"], "charts": len(u["final_response"]["charts"])})
def response(state: dict) -> dict:
    from app.schemas.api_response import ChatResponse

    plan = state["analytical_plan"]
    tool_results = state.get("tool_results", {})
    expl = state.get("explanation", {})
    metrics = [m for r in tool_results.values() for m in r.get("metrics", []) if m.get("unit") != "p"][:12]
    rankings = []
    for op in ("top_statements", "leadership_priorities", "rank_negative_topics", "topic_frequency"):
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
        model_metadata=(mm := _model_metadata(state)), routing=mm["routing"] or {}, token_usage=mm["token_usage"], quality_status=state.get("qa_results", {}),
        governance=state.get("governance_findings", []),
        dashboard=state.get("dashboard"), evidence_review=state.get("evidence_review"), xray=_panel(tool_results.get("conversation_xray")), root_cause=_panel(tool_results.get("root_cause_investigation")),
        groundedness=state.get("groundedness"),
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
