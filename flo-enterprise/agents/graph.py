"""LangGraph orchestration.

Ask-Flo graph (a DAG - no agent-to-agent loops; recursion_limit bounds execution):
    guard -> enterprise_supervisor -> {executive|investment|wealth|risk_compliance|ai_operations}_supervisor
          -> Send(specialist) x N (parallel, independent tasks only) -> synthesize -> END

Client-communication graph (durable human-in-the-loop, SqliteSaver checkpoints):
    draft -> precheck -> request_approval -> await_approval (interrupt) -> execute -> END
"""
from __future__ import annotations

import operator
import re
import sqlite3
import threading
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, Send, interrupt

import agents.specialists  # noqa: F401 (registers agents)
from backend.config import get_settings
from governance import audit
from harness.context import RunContext
from harness.errors import HarnessError
from harness.registry import REGISTRY
from harness.runtime import get_harness
from retrieval.injection import scan_text
from retrieval.language import detect_language

RUNS: dict[str, RunContext] = {}
_runs_lock = threading.Lock()

HEADINGS = {"en": "FLO answer", "fr": "Réponse de FLO", "es": "Respuesta de FLO", "hi": "FLO उत्तर", "ta": "FLO பதில்", "ko": "FLO 답변"}
LANG_NOTE = {"en": "", "fr": "Note : la narration détaillée est fournie en anglais en mode modèle simulé ; les chiffres et citations sont préservés.",
             "es": "Nota: la narración detallada se ofrece en inglés en modo de modelo simulado; cifras y citas se conservan.",
             "hi": "नोट: मॉक मॉडल मोड में विस्तृत विवरण अंग्रेज़ी में है; संख्याएँ और उद्धरण सुरक्षित हैं।",
             "ta": "குறிப்பு: மாதிரி மாதிரி முறையில் விரிவான விளக்கம் ஆங்கிலத்தில் உள்ளது; எண்கள் மற்றும் மேற்கோள்கள் பாதுகாக்கப்படுகின்றன.",
             "ko": "참고: 모의 모델 모드에서는 상세 설명이 영어로 제공되며 수치와 인용은 그대로 유지됩니다."}

CHART_AGENTS = {"aum_trend": ["aum_agent"], "aum_waterfall": ["aum_agent"], "revenue_expenses": ["financial_performance_agent"],
                "net_flows": ["aum_agent"], "product_profitability": ["revenue_agent"], "margin_trend": ["financial_performance_agent", "revenue_agent"],
                "risk_heatmap": ["risk_agent"], "geographic_exposure": ["portfolio_agent"], "actual_vs_budget": ["board_reporting_agent"],
                "initiative_scorecard": ["decision_memory_agent"], "performance": ["portfolio_agent"], "concentration": ["portfolio_agent", "risk_agent"],
                "scenario": ["scenario_agent"], "benchmarks": ["market_intelligence_agent"], "relative_return": ["benchmark_agent"],
                "correlation": ["risk_agent"], "retirement_projection": ["retirement_planning_agent"], "agent_failures": ["operational_intelligence_agent"],
                "data_quality": ["data_quality_agent"], "decision_timeline": ["decision_memory_agent"]}

RULES: list[tuple[str, str, list[str]]] = [  # (regex, domain, agents) evaluated in order; first domain wins, agents accumulate
    (r"(aum|assets under management).*(profit|margin)|(profit|margin).*(aum|assets under management)", "executive",
     ["aum_agent", "financial_performance_agent", "revenue_agent"]),
    (r"board (report|pack)|prepare.*board", "executive", ["board_reporting_agent"]),
    (r"decision|initiative|commitment|assumption|behind schedule|delivered", "executive", ["decision_memory_agent"]),
    (r"agent (fail|error)|failure|incident|latency|trace|circuit|outage|timeout", "ai_operations", ["operational_intelligence_agent"]),
    (r"data quality|reconcil.*check|quality check", "ai_operations", ["data_quality_agent"]),
    (r"\beval|release gate", "ai_operations", ["evaluation_agent"]),
    (r"shock|scenario|stress|simulat|what if|crash|downturn|bear|bull", "investment", ["scenario_agent"]),
    (r"concentrat|exposure|single[- ]issuer|holding", "investment", ["portfolio_agent"]),
    (r"benchmark|outperform|underperform|relative", "investment", ["benchmark_agent"]),
    (r"market|sector|index", "investment", ["market_intelligence_agent"]),
    (r"research|outlook|thesis", "investment", ["investment_research_agent"]),
    (r"\bC-\d{5}\b|client review|meeting|prepare.*client|portfolio review", "wealth",
     ["client_intelligence_agent", "wealth_advisor_agent", "retirement_planning_agent", "client_meeting_agent"]),
    (r"retire", "wealth", ["retirement_planning_agent"]),
    (r"product|fund|etf|compare.*fee|fee comparison", "wealth", ["product_research_agent"]),
    (r"policy|regulat|complian|suitab|aml|privacy|kyc|ciro|communications? (rule|policy)|approval|conformit|cumplimiento", "risk_compliance",
     ["compliance_research_agent"]),
    (r"risk|correlat|heat ?map|drawdown", "risk_compliance", ["risk_agent"]),
    (r"revenue|yield|fee", "executive", ["revenue_agent"]),
    (r"margin|profit|expense|cost", "executive", ["financial_performance_agent"]),
    (r"aum|flow|asset growth", "executive", ["aum_agent"]),
]
ROLE_DEFAULT = {"executive": ("executive", ["aum_agent"]), "finance": ("executive", ["financial_performance_agent"]),
                "cio": ("investment", ["portfolio_agent"]), "investment_analyst": ("investment", ["market_intelligence_agent"]),
                "wealth_advisor": ("wealth", ["product_research_agent"]), "external_advisor": ("wealth", ["product_research_agent"]),
                "compliance_officer": ("risk_compliance", ["compliance_research_agent"]), "privacy_officer": ("risk_compliance", ["compliance_research_agent"]),
                "ai_admin": ("ai_operations", ["operational_intelligence_agent"]), "risk_officer": ("risk_compliance", ["risk_agent"]),
                "prospect": ("wealth", ["product_research_agent"])}
SUPERVISORS = ["executive", "investment", "wealth", "risk_compliance", "ai_operations"]


class AskState(TypedDict, total=False):
    workflow_id: str
    question: str
    language: str
    context: dict
    guard: dict
    route: str
    candidate_agents: list[str]
    plan: list[dict]
    results: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]
    answer: dict


def _ctx(state) -> RunContext:
    return RUNS[state["workflow_id"]]


def guard(state: AskState) -> dict:
    ctx = _ctx(state)
    q = state["question"]
    inj = scan_text(q)
    lang = state.get("language") or detect_language(q)
    if len(q) > get_settings().max_input_chars:
        return {"guard": {"blocked": True, "reason": "INPUT-TOO-LARGE", "injection": inj}, "language": lang}
    if inj["flagged"]:
        audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="ask.injection_detected", resource_type="workflow",
                     resource_id=ctx.workflow_id, decision="flag", reasons=[{"rule": "INJECTION-SCAN", "hits": [h["pattern"] for h in inj["hits"]]}],
                     policy_version=ctx.engine.version, details={"question": q[:300]})
    return {"guard": {"blocked": False, "injection": inj}, "language": lang}


def enterprise_supervisor(state: AskState) -> dict:
    ctx = _ctx(state)
    q = state["question"]
    chart = (state.get("context") or {}).get("chart_id")
    hint = (state.get("context") or {}).get("route_hint") or {}
    domain, agents = None, []
    if hint.get("domain") in SUPERVISORS and hint.get("agents") and all(a in REGISTRY.agents for a in hint["agents"]):
        # conversational intent planner chose the agents; the supervisor still filters by role and input below
        domain, agents = hint["domain"], list(hint["agents"])
    elif chart in CHART_AGENTS:
        agents = list(CHART_AGENTS[chart])
        domain = REGISTRY.get(agents[0]).spec.domain
    else:
        for rx, dom, ags in RULES:
            if re.search(rx, q, re.IGNORECASE):
                if domain is None:
                    domain = dom
                if dom == domain or domain == "executive" and dom == "executive":
                    agents += [a for a in ags if a not in agents]
    if not agents:
        for r in ctx.principal.roles:
            if r in ROLE_DEFAULT:
                domain, agents = ROLE_DEFAULT[r]
                break
    domain = {"aiops": "ai_operations", "risk": "risk_compliance"}.get(domain or "executive", domain or "executive")
    return {"route": domain, "candidate_agents": agents[:5]}


def _make_supervisor(name: str):
    def node(state: AskState) -> dict:
        ctx = _ctx(state)
        q = state["question"]
        cid = re.search(r"\bC-\d{5}\b", q)
        pid = re.search(r"\bPF-\d{4}\b", q)
        ctxd = state.get("context") or {}
        months = int(ctxd["months"]) if str(ctxd.get("months", "")).isdigit() and 1 <= int(ctxd["months"]) <= 24 else \
            24 if re.search(r"24|two years|2 years", q) else 12
        scen = ctxd.get("scenario") or {}
        plan, skipped = [], []
        for a in state.get("candidate_agents", []):
            spec = REGISTRY.get(a).spec
            if not set(ctx.principal.roles) & spec.allowed_roles:
                skipped.append(a)
                continue
            inp: dict[str, Any] = {"question": q[:4000], "months": months, "language": state["language"]}
            if spec.input_model.__name__ == "ClientQ":
                client_id = (cid.group(0) if cid else None) or ctxd.get("client_id")
                if not client_id:
                    skipped.append(a)
                    continue
                inp["client_id"] = client_id
                if a == "client_meeting_agent" and re.search(r"draft|email|letter|message", q, re.I):
                    inp["draft_language"] = ctxd.get("draft_language") or state["language"]
            if spec.input_model.__name__ == "PortfolioQ":
                inp["portfolio_id"] = (pid.group(0) if pid else None) or ctxd.get("portfolio_id")
            if spec.input_model.__name__ == "FirmQ":
                prof = ctxd.get("business_profile") or {}
                inp.update({k: prof[k] for k in ("aum", "fee_bps", "revenue", "expenses", "advisors", "clients", "net_flows") if prof.get(k) is not None})
            if spec.input_model.__name__ == "ScenarioQ" and scen:
                inp.update({k: scen[k] for k in ("preset", "equity_shock", "rate_shock_bps") if scen.get(k) is not None})
            elif spec.input_model.__name__ == "ScenarioQ":
                inp["preset"] = "severe_stress" if re.search(r"severe|crash|crisis", q, re.I) else "bear" if re.search(r"bear|shock|downturn|drop|fall|decline", q, re.I) \
                    else "bull" if re.search(r"bull|rally", q, re.I) else "base"
                m = re.search(r"(-?\d{1,2})\s?%", q)
                if m and re.search(r"equit|stock|market", q, re.I):
                    v = int(m.group(1))
                    inp["equity_shock"] = (-abs(v) if re.search(r"drop|fall|declin|shock|crash|down", q, re.I) else v) / 100
            plan.append({"agent": a, "input": inp})
        if skipped:
            audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action=f"route.{name}", resource_type="workflow",
                         resource_id=ctx.workflow_id, decision="partial" if plan else "deny",
                         reasons=[{"rule": "AGENT-ROLE-OR-INPUT", "skipped": skipped}], policy_version=ctx.engine.version)
        return {"plan": plan, "errors": [{"agent": a, "failure_class": "not_authorized_or_missing_input", "message":
                                          f"{a} not available for your role or missing a required identifier"} for a in skipped]}
    node.__name__ = f"{name}_supervisor"
    return node


def specialist(task: dict) -> dict:
    ctx = RUNS[task["workflow_id"]].fork()
    try:
        out = get_harness().run(task["agent"], ctx, task["input"])
        return {"results": [out.model_dump()]}
    except HarnessError as e:
        return {"errors": [{"agent": task["agent"], "failure_class": e.failure_class, "code": e.code, "message": str(e)[:300]}]}
    except Exception as e:  # noqa: BLE001 - isolate one branch's failure from the others
        return {"errors": [{"agent": task["agent"], "failure_class": "internal_error", "message": e.__class__.__name__}]}


def fan_out(state: AskState):
    if not state.get("plan"):
        return "synthesize"
    return [Send("specialist", {"workflow_id": state["workflow_id"], **p}) for p in state["plan"]]


def synthesize(state: AskState) -> dict:
    ctx = _ctx(state)
    lang = state.get("language", "en")
    order = {p["agent"]: i for i, p in enumerate(state.get("plan", []))}
    results = sorted(state.get("results", []), key=lambda r: order.get(r["agent"], 99))
    g = state.get("guard", {})
    if g.get("blocked"):
        text = f"Request rejected at admission: {g['reason']}."
    elif not results:
        text = "FLO could not produce an authorized, evidence-backed answer for this request." + (
            " " + "; ".join(e["message"] for e in state.get("errors", [])) if state.get("errors") else "")
    else:
        text = "\n\n".join(r["narrative"] for r in results)
    cites, seen = [], set()
    for r in results:
        for c in r.get("citations", []):
            key = (c["document_id"], c["section"])
            if key not in seen:
                seen.add(key)
                cites.append(c)
    approvals = [r["approval"] for r in results if r.get("approval")] + ctx.approvals
    return {"answer": {"heading": HEADINGS.get(lang, HEADINGS["en"]), "language": lang, "language_note": LANG_NOTE.get(lang, ""),
                       "text": text, "route": state.get("route"), "agents": [r["agent"] for r in results], "results": results,
                       "errors": state.get("errors", []), "citations": cites, "approvals": approvals,
                       "warnings": [w for r in results for w in r.get("warnings", [])],
                       "injection": g.get("injection"), "charts": sorted({c for r in results for c in r.get("charts", [])})}}


def _after_guard(state: AskState):
    return "synthesize" if state["guard"].get("blocked") else "enterprise_supervisor"


def build_ask_graph():
    g = StateGraph(AskState)
    g.add_node("guard", guard)
    g.add_node("enterprise_supervisor", enterprise_supervisor)
    for s in SUPERVISORS:
        g.add_node(f"{s}_supervisor", _make_supervisor(s))
        g.add_conditional_edges(f"{s}_supervisor", fan_out, ["specialist", "synthesize"])
    g.add_node("specialist", specialist)
    g.add_node("synthesize", synthesize)
    g.add_edge(START, "guard")
    g.add_conditional_edges("guard", _after_guard, ["enterprise_supervisor", "synthesize"])
    g.add_conditional_edges("enterprise_supervisor", lambda s: f"{s['route']}_supervisor", [f"{s}_supervisor" for s in SUPERVISORS])
    g.add_edge("specialist", "synthesize")
    g.add_edge("synthesize", END)
    return g.compile(checkpointer=MemorySaver())


_ask_graph = None


def ask(ctx: RunContext, question: str, context: dict | None = None, language: str | None = None, on_event=None) -> dict:
    """Run the Ask graph. `on_event(node, update)` receives each node's update as it completes (real progress, used for streaming)."""
    global _ask_graph
    if _ask_graph is None:
        _ask_graph = build_ask_graph()
    harness = get_harness()
    harness.admit(ctx)
    with _runs_lock:
        RUNS[ctx.workflow_id] = ctx
    ans = None
    try:
        for chunk in _ask_graph.stream({"workflow_id": ctx.workflow_id, "question": question, "language": language or "", "context": context or {},
                                        "results": [], "errors": []},
                                       config={"configurable": {"thread_id": ctx.workflow_id}, "recursion_limit": 25}, stream_mode="updates"):
            for node, update in chunk.items():
                if node == "synthesize":
                    ans = update["answer"]
                if on_event is not None:
                    on_event(node, update or {})
    finally:
        with _runs_lock:
            RUNS.pop(ctx.workflow_id, None)
        harness.release(ctx)
    ans.update(workflow_id=ctx.workflow_id, trace_ids=ctx.trace_ids, tool_calls=ctx.tool_log, policy_decisions=ctx.policy_log,
               model=ctx.model.name, model_mode="mock-deterministic (no external LLM calls)" if ctx.model.name.startswith("mock") else ctx.model.name)
    audit.record(tenant_id=ctx.principal.tenant_id, actor=ctx.principal.user_id, action="ask.completed", resource_type="workflow",
                 resource_id=ctx.workflow_id, decision="allow" if ans["results"] else "deny", policy_version=ctx.engine.version,
                 details={"route": ans["route"], "agents": ans["agents"], "errors": [e.get("failure_class") for e in ans["errors"]]})
    return ans


# =========================================================================================== communication workflow
class CommsState(TypedDict, total=False):
    workflow_id: str
    client_id: str
    language: str
    requester: str
    draft: dict
    precheck: dict
    approval_id: str
    payload: dict
    status: str
    result: dict


COMMS_CTX: dict[str, RunContext] = {}


def _comms_ctx(state) -> RunContext:
    return COMMS_CTX[state["workflow_id"]]


def c_draft(state: CommsState) -> dict:
    ctx = _comms_ctx(state)
    out = get_harness().run("client_meeting_agent", ctx, {"client_id": state["client_id"], "question": "draft portfolio review follow-up",
                                                         "draft_language": state["language"], "language": state["language"]})
    return {"draft": out.facts["draft"]}


def c_precheck(state: CommsState) -> dict:
    d = state["draft"]
    ok = d["translation_validation"]["valid"] and d["compliance_precheck"]["passed"]
    return {"precheck": {"passed": ok, "translation": d["translation_validation"], "compliance": d["compliance_precheck"]},
            "status": "precheck_passed" if ok else "blocked_precheck"}


def c_request(state: CommsState) -> dict:
    from approvals.service import ApprovalService
    from backend.db.session import session_scope
    from governance import resources
    ctx = _comms_ctx(state)
    d = state["draft"]
    payload = {"to": f"client:{state['client_id']}", "subject": d["subject"], "body": d["body"], "language": d["language"],
               "template_version": d["template_version"]}
    svc = ApprovalService(ctx.engine, lambda tid, ref: resources.from_ref(ctx.adapters.store, tid, ref))
    with session_scope() as s:
        a = svc.request(s, ctx.principal, "comms:send", f"client:{state['client_id']}", payload,
                        [{"type": "draft_facts", "facts": d["facts"]}, {"type": "precheck", **state["precheck"]}], thread_id=state["workflow_id"])
        aid = a.id
    return {"approval_id": aid, "payload": payload, "status": "awaiting_approval"}


def c_await(state: CommsState) -> dict:
    decision = interrupt({"approval_id": state["approval_id"], "message": "Awaiting compliance approval of the exact payload."})
    return {"payload": decision.get("payload", state["payload"]), "status": "resumed"}


def c_execute(state: CommsState) -> dict:
    from approvals.service import ApprovalError, ApprovalService, to_dict
    from backend.db.session import session_scope
    from governance import resources
    ctx = _comms_ctx(state)
    svc = ApprovalService(ctx.engine, lambda tid, ref: resources.from_ref(ctx.adapters.store, tid, ref))
    with session_scope() as s:
        try:
            a = svc.execute(s, ctx.principal, state["approval_id"], state["payload"])
            return {"status": "executed", "result": to_dict(a)["execution_result"]}
        except ApprovalError as e:
            return {"status": f"execution_denied:{e.code}", "result": {"code": e.code, "message": str(e)}}


def build_comms_graph(checkpointer):
    g = StateGraph(CommsState)
    for n, f in [("draft", c_draft), ("precheck", c_precheck), ("request_approval", c_request), ("await_approval", c_await), ("execute", c_execute)]:
        g.add_node(n, f)
    g.add_edge(START, "draft")
    g.add_edge("draft", "precheck")
    g.add_conditional_edges("precheck", lambda s: "request_approval" if s["precheck"]["passed"] else END, ["request_approval", END])
    g.add_edge("request_approval", "await_approval")
    g.add_edge("await_approval", "execute")
    g.add_edge("execute", END)
    return g.compile(checkpointer=checkpointer)


_comms_graph = None
_comms_lock = threading.Lock()


def comms_graph():
    global _comms_graph
    with _comms_lock:
        if _comms_graph is None:
            path = Path(get_settings().checkpoint_db)
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(path), check_same_thread=False)
            _comms_graph = build_comms_graph(SqliteSaver(conn))
        return _comms_graph


def start_communication(ctx: RunContext, client_id: str, language: str) -> dict:
    COMMS_CTX[ctx.workflow_id] = ctx
    try:
        out = comms_graph().invoke({"workflow_id": ctx.workflow_id, "client_id": client_id, "language": language, "requester": ctx.principal.user_id},
                                   config={"configurable": {"thread_id": ctx.workflow_id}, "recursion_limit": 20})
    finally:
        COMMS_CTX.pop(ctx.workflow_id, None)
    return {"thread_id": ctx.workflow_id, "status": out.get("status"), "approval_id": out.get("approval_id"), "draft": out.get("draft"),
            "precheck": out.get("precheck"), "interrupted": "__interrupt__" in out}


def resume_communication(ctx: RunContext, thread_id: str, payload: dict | None = None) -> dict:
    graph = comms_graph()
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": 20}
    snap = graph.get_state(cfg)
    if not snap.values or snap.values.get("requester") != ctx.principal.user_id:
        raise PermissionError("unknown workflow or not the requester")
    ctx.workflow_id = thread_id
    COMMS_CTX[thread_id] = ctx
    try:
        resume = {"action": "execute", **({"payload": payload} if payload is not None else {})}  # must be non-empty for LangGraph
        out = graph.invoke(Command(resume=resume), config=cfg)
    finally:
        COMMS_CTX.pop(thread_id, None)
    return {"thread_id": thread_id, "status": out.get("status"), "result": out.get("result"), "approval_id": out.get("approval_id")}
