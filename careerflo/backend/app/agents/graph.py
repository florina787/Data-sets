"""LangGraph supervisor and specialised agents.

Graph:  START -> supervisor -> (agent)* -> governance -> END

* ``supervisor`` classifies intent deterministically, extracts parameters and builds a bounded plan.
* ``dispatch`` (conditional edge) sends control to the next planned agent, or to ``governance``.
* Every agent reaches tools only through ``mcp_gateway.call_tool`` with its own allowlist.
* ``governance`` validates outputs (injection flags, unsupported claims, approvals) before the
  response is composed. Bounds: max 6 agents per plan, max 24 tool calls per run, LangGraph
  recursion limit 30, and per-tool timeouts in the gateway.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from .. import mcp_gateway as gw
from ..careers import ats as ATS
from ..careers import cover_letter as CL
from ..careers import interview as IV
from ..careers.coding import public_exercises
from ..careers.context import NotFound, get_resume
from ..careers.salary import negotiation_scenarios
from ..db import SessionLocal
from ..models import AgentRun, Profile, Recruiter, RecruiterInteraction
from .intents import AGENT_LABELS, classify, extract_params

MAX_PLAN = 6
MAX_TOOL_CALLS = 24
RECURSION_LIMIT = 30


class CareerState(TypedDict, total=False):
    user_id: str
    run_id: str
    message: str
    intent: str
    params: dict[str, Any]
    plan: list[str]
    cursor: int
    results: dict[str, Any]
    cards: list[dict[str, Any]]
    notes: list[str]
    warnings: list[str]
    approvals: list[dict[str, Any]]
    steps: list[dict[str, Any]]
    tool_calls: int
    status: str


class Budget(Exception):
    pass


async def _tool(state: CareerState, agent: str, server: str, tool: str, args: dict[str, Any]) -> Any:
    if state.get("tool_calls", 0) >= MAX_TOOL_CALLS:
        raise Budget("tool-call budget for this run is exhausted")
    state["tool_calls"] = state.get("tool_calls", 0) + 1
    t0 = time.perf_counter()
    res = await gw.call_tool(uuid.UUID(state["user_id"]), agent, server, tool, args, run_id=uuid.UUID(state["run_id"]))
    state.setdefault("steps", []).append({"agent": agent, "tool": f"{server}.{tool}", "ms": int((time.perf_counter() - t0) * 1000),
                                          "status": "ok"})
    return res.data


def _top_job(state: CareerState) -> dict[str, Any] | None:
    ranked = state.get("results", {}).get("job_matching", {}).get("ranked") or []
    if ranked:
        return ranked[0]["job"]
    jobs = state.get("results", {}).get("job_discovery", {}).get("jobs") or []
    return jobs[0] if jobs else None


# ---------------------------------------------------------------- supervisor
def supervisor(state: CareerState) -> CareerState:
    msg = state["message"]
    plan = classify(msg)
    if plan == ["autonomous_workflow"]:
        intent = "autonomous_workflow"
    elif not plan:
        intent = "general"
    else:
        intent = "multi_agent" if len(plan) > 1 else plan[0]
    params = extract_params(msg)
    # A matching/resume/interview request that also asks to *find* jobs needs discovery first.
    if any(a in plan for a in ("job_matching",)) and "job_discovery" not in plan and params.get("query"):
        plan = ["job_discovery", *plan]
    return {"intent": intent, "plan": plan[:MAX_PLAN], "params": params, "cursor": 0, "results": {}, "cards": [],
            "notes": [], "warnings": [], "approvals": [], "steps": [{"agent": "supervisor", "intent": intent, "plan": plan[:MAX_PLAN]}],
            "tool_calls": 0, "status": "running"}


def dispatch(state: CareerState) -> str:
    plan, cur = state.get("plan", []), state.get("cursor", 0)
    return plan[cur] if cur < len(plan) else "governance"


def _advance(state: CareerState, agent: str, result: Any = None, card: dict | None = None, note: str | None = None) -> CareerState:
    out: CareerState = {"cursor": state.get("cursor", 0) + 1, "results": {**state.get("results", {}), agent: result or {}},
                        "cards": state.get("cards", []) + ([card] if card else []),
                        "notes": state.get("notes", []) + ([note] if note else []),
                        "steps": state.get("steps", []), "tool_calls": state.get("tool_calls", 0),
                        "approvals": state.get("approvals", []), "warnings": state.get("warnings", [])}
    return out


def _guard(agent: str):
    """Wrap an agent so a failure is reported and the workflow continues (error recovery)."""
    def deco(fn):
        async def wrapper(state: CareerState) -> CareerState:
            try:
                return await fn(state)
            except (gw.ToolDenied, gw.ToolFailed, NotFound, Budget, LookupError, ValueError) as exc:
                state.setdefault("steps", []).append({"agent": agent, "status": "error", "error": str(exc)[:300]})
                return _advance(state, agent, {"error": str(exc)[:300]}, note=f"{AGENT_LABELS[agent]}: {str(exc)[:200]}")
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


# ---------------------------------------------------------------- agents
@_guard("job_discovery")
async def job_discovery(state: CareerState) -> CareerState:
    p = state["params"]
    args = {k: p[k] for k in ("query", "city", "work_arrangement", "salary_min", "currency", "seniority", "company") if p.get(k)}
    if p.get("seniority"):
        args.pop("seniority")  # seniority is already part of the title query; avoid over-filtering
    if p.get("origin"):
        tool = "search_indeed_origin_jobs" if p["origin"] == "indeed" else "search_linkedin_origin_jobs"
        args = {k: v for k, v in args.items() if k in ("query", "city", "salary_min", "currency")}
        args.setdefault("query", "software engineer")
        data = await _tool(state, "job_discovery", "jobs", tool, args)
    else:
        data = await _tool(state, "job_discovery", "jobs", "search_all_jobs", args | {"limit": 20})
    jobs = data.get("jobs", [])
    note = None
    if not jobs:
        note = "No postings matched every filter. Try widening the salary or location filters."
    configured = {k: v for k, v in (data.get("providers") or {}).items()}
    return _advance(state, "job_discovery", data, {"type": "jobs", "title": f"{len(jobs)} jobs found", "jobs": jobs[:12],
                                                   "providers": configured, "filter_stats": data.get("filter_stats"),
                                                   "synthetic": data.get("synthetic_included", False)}, note)


@_guard("job_matching")
async def job_matching(state: CareerState) -> CareerState:
    jobs = state.get("results", {}).get("job_discovery", {}).get("jobs") or []
    if not jobs:
        return _advance(state, "job_matching", {"ranked": []}, note="Job Matching needs jobs: run a search first.")
    ranked = []
    for j in jobs[:6]:
        m = await _tool(state, "job_matching", "resume", "compare_resume_to_job", {"job_id": j["id"]})
        ranked.append({"job": j, "match": {k: m[k] for k in ("score", "grade", "components", "matched_required", "missing_required", "methodology")}})
    ranked.sort(key=lambda r: -r["match"]["score"])
    return _advance(state, "job_matching", {"ranked": ranked},
                    {"type": "ranking", "title": "Best opportunities for your verified profile", "ranked": ranked,
                     "methodology": ranked[0]["match"]["methodology"] if ranked else None})


@_guard("resume_intelligence")
async def resume_intelligence(state: CareerState) -> CareerState:
    job = _top_job(state)
    wants_tailor = any(w in state["message"].lower() for w in ("tailor", "optimi", "rewrite", "for this position", "for this job"))
    if job and wants_tailor:
        data = await _tool(state, "resume_intelligence", "resume", "tailor_resume", {"job_id": job["id"]})
        return _advance(state, "resume_intelligence", data, {
            "type": "resume", "title": f"Tailored resume — {job['title']} at {job['company']}", "version_id": data["version_id"],
            "text": data["text"], "gaps": data["tailored"]["gaps"], "questions": data["tailored"]["clarifying_questions"],
            "validation": data["validation"], "downloads": data["downloads"]})
    data = await _tool(state, "resume_intelligence", "resume", "analyze_resume", {})
    return _advance(state, "resume_intelligence", data, {"type": "resume_analysis", "title": "Resume analysis", **data})


@_guard("ats_intelligence")
async def ats_intelligence(state: CareerState) -> CareerState:
    job = _top_job(state)
    with SessionLocal() as db:
        r = get_resume(db, uuid.UUID(state["user_id"]))
        job_full = None
        if job:
            job_full = await _tool(state, "ats_intelligence", "company", "analyze_job_requirements", {"job_id": job["id"]})
            job_full["description"] = ""
        report = ATS.ats_check(r.original_text, r.parsed, job_full)
    return _advance(state, "ats_intelligence", report, {"type": "ats", "title": "ATS simulation", **report})


@_guard("cover_letter")
async def cover_letter(state: CareerState) -> CareerState:
    job = _top_job(state)
    if not job:
        return _advance(state, "cover_letter", {}, note="Cover letters need a target job: search or pick one first.")
    with SessionLocal() as db:
        r = get_resume(db, uuid.UUID(state["user_id"]))
        letter = CL.draft_cover_letter(r.parsed, job)
        msg = CL.recruiter_message(r.parsed, job)
    check = await _tool(state, "cover_letter", "resume", "validate_resume_claims", {"text": letter})
    return _advance(state, "cover_letter", {"letter": letter, "validation": check},
                    {"type": "letter", "title": f"Cover letter — {job['title']}", "letter": letter, "recruiter_message": msg,
                     "validation": check})


@_guard("interview")
async def interview(state: CareerState) -> CareerState:
    p = state["params"]
    role = p.get("role") or (_top_job(state) or {}).get("title") or "Software Engineer"
    qs = IV.plan_interview(role, p.get("topics"), 6)
    return _advance(state, "interview", {"role": role, "questions": qs},
                    {"type": "interview", "title": f"Interview plan — {role}", "role": role,
                     "questions": [{"topic": x["topic"], "question": x["question"], "kind": x["kind"]} for x in qs],
                     "cta": "Start an interactive mock interview in Interview Intelligence to get scored feedback."})


@_guard("coding_coach")
async def coding_coach(state: CareerState) -> CareerState:
    ex = public_exercises()
    return _advance(state, "coding_coach", {"exercises": ex}, {"type": "coding", "title": "Coding exercises", "exercises": ex})


@_guard("company_research")
async def company_research(state: CareerState) -> CareerState:
    company = state["params"].get("company") or (_top_job(state) or {}).get("company")
    if not company:
        return _advance(state, "company_research", {}, note="Which company should I research? e.g. 'Research Shopify'.")
    data = await _tool(state, "company_research", "company", "retrieve_company_information", {"company": company})
    return _advance(state, "company_research", data, {"type": "company", "title": f"Company brief — {company}", **data})


@_guard("recruiter_crm")
async def recruiter_crm(state: CareerState) -> CareerState:
    uid = uuid.UUID(state["user_id"])
    with SessionLocal() as db:
        recs = list(db.scalars(select(Recruiter).where(Recruiter.user_id == uid).limit(50)))
        out = []
        for r in recs:
            last = db.scalar(select(RecruiterInteraction).where(RecruiterInteraction.recruiter_id == r.id)
                             .order_by(RecruiterInteraction.occurred_at.desc()))
            days = None
            if last:
                from ..models import utcnow
                occ = last.occurred_at if last.occurred_at.tzinfo else last.occurred_at.replace(tzinfo=__import__("datetime").timezone.utc)
                days = (utcnow() - occ).days
            out.append({"id": str(r.id), "name": r.name, "company": r.company, "last_contact_days": days,
                        "suggest_follow_up": days is None or days >= 7, "is_synthetic": r.is_synthetic})
    return _advance(state, "recruiter_crm", {"recruiters": out}, {"type": "recruiters", "title": "Recruiter follow-ups", "recruiters": out})


@_guard("application_tracker")
async def application_tracker(state: CareerState) -> CareerState:
    data = await _tool(state, "application_tracker", "applications", "list_applications", {})
    return _advance(state, "application_tracker", data, {"type": "applications", "title": "Your applications", **data})


@_guard("portfolio")
async def portfolio(state: CareerState) -> CareerState:
    username = state["params"].get("github_username")
    if not username:
        with SessionLocal() as db:
            prof = db.scalar(select(Profile).where(Profile.user_id == uuid.UUID(state["user_id"])))
            username = prof.github_username if prof else None
    if not username:
        return _advance(state, "portfolio", {}, note="Add your GitHub username in Account Settings (or mention github.com/<you>).")
    stack = await _tool(state, "portfolio", "portfolio", "analyze_technology_stack", {"username": username})
    job = _top_job(state)
    matches = None
    if job:
        matches = await _tool(state, "portfolio", "portfolio", "match_project_to_job", {"username": username, "job_id": job["id"]})
    return _advance(state, "portfolio", {"stack": stack, "matches": matches},
                    {"type": "portfolio", "title": f"GitHub portfolio — {username}", "stack": stack, "matches": matches})


@_guard("salary")
async def salary(state: CareerState) -> CareerState:
    p = state["params"]
    kw = (p.get("query") or p.get("role") or "").replace("Senior ", "").replace("senior ", "")
    dist = await _tool(state, "salary", "analytics", "analyze_salary_distribution",
                       {"title_keyword": kw.split()[-1] if kw else "", "currency": p.get("currency"), "city": p.get("city")})
    scen = negotiation_scenarios(p["offer"], dist) if p.get("offer") else None
    return _advance(state, "salary", {"distribution": dist, "negotiation": scen},
                    {"type": "salary", "title": "Published salary benchmarks", "distribution": dist, "negotiation": scen})


@_guard("career_analytics")
async def career_analytics(state: CareerState) -> CareerState:
    data = await _tool(state, "career_analytics", "analytics", "generate_dashboard_data", {})
    return _advance(state, "career_analytics", data, {"type": "analytics", "title": "Career analytics", "dashboard": data})


@_guard("autonomous_workflow")
async def autonomous_workflow(state: CareerState) -> CareerState:
    p = state["params"]
    args = {k: p[k] for k in ("query", "city", "salary_min", "currency", "work_arrangement") if p.get(k)}
    found = await _tool(state, "autonomous_workflow", "jobs", "search_all_jobs", args | {"limit": 10})
    jobs = found.get("jobs", [])
    if not jobs:
        return _advance(state, "autonomous_workflow", found, note="No matching jobs found for the workflow.")
    scored = []
    for j in jobs[:4]:
        m = await _tool(state, "autonomous_workflow", "resume", "compare_resume_to_job", {"job_id": j["id"]})
        scored.append((m["score"], j, m))
    scored.sort(key=lambda x: -x[0])
    score, job, match = scored[0]
    tailored = await _tool(state, "autonomous_workflow", "resume", "tailor_resume", {"job_id": job["id"]})
    app = await _tool(state, "autonomous_workflow", "applications", "create_application",
                      {"company": job["company"], "title": job["title"], "job_id": job["id"],
                       "notes": f"Prepared by Career_flo workflow; match {score}"})
    upd = await _tool(state, "autonomous_workflow", "applications", "update_application", {"application_id": app["id"], "status": "applied"})
    approvals = state.get("approvals", []) + ([{"approval_id": upd["approval_id"], "action": "submit_application",
                                                "summary": f"Submit application: {job['title']} at {job['company']}"}] if upd.get("approval_required") else [])
    st = _advance(state, "autonomous_workflow", {"job": job, "match": match, "version_id": tailored["version_id"], "application": app},
                  {"type": "workflow", "title": "Application package prepared — awaiting your approval",
                   "job": job, "score": score, "version_id": tailored["version_id"], "downloads": tailored["downloads"],
                   "application_id": app["id"], "approval_id": upd.get("approval_id"),
                   "steps": ["Searched jobs", f"Scored {len(scored)} top postings", "Tailored resume (fact-checked)",
                             "Created draft application", "Requested your approval to mark it submitted"]})
    st["approvals"] = approvals
    return st


async def governance(state: CareerState) -> CareerState:
    warnings = list(state.get("warnings", []))
    for agent, res in (state.get("results") or {}).items():
        if not isinstance(res, dict):
            continue
        val = res.get("validation")
        if isinstance(val, dict):
            final = val.get("final", val)
            if isinstance(final, dict) and final.get("issues"):
                warnings.append(f"{AGENT_LABELS.get(agent, agent)}: {len(final['issues'])} statement(s) not supported by your resume were flagged.")
        overview = res.get("overview") if isinstance(res.get("overview"), dict) else None
        if overview and overview.get("injection_flags"):
            warnings.append("External content contained instruction-like text; it was neutralised and ignored.")
    if any(c.get("synthetic") or c.get("is_synthetic") for c in state.get("cards", [])):
        warnings.append("Some results are synthetic demo data (clearly labelled) because live providers are not configured.")
    steps = state.get("steps", []) + [{"agent": "governance", "status": "ok", "warnings": len(warnings)}]
    status = "awaiting_approval" if state.get("approvals") else "completed"
    return {"warnings": warnings, "steps": steps, "status": status}


AGENT_NODES = {
    "job_discovery": job_discovery, "job_matching": job_matching, "resume_intelligence": resume_intelligence,
    "ats_intelligence": ats_intelligence, "cover_letter": cover_letter, "interview": interview, "coding_coach": coding_coach,
    "company_research": company_research, "recruiter_crm": recruiter_crm, "application_tracker": application_tracker,
    "portfolio": portfolio, "salary": salary, "career_analytics": career_analytics, "autonomous_workflow": autonomous_workflow,
}


def build_graph():
    g = StateGraph(CareerState)
    g.add_node("supervisor", supervisor)
    for name, fn in AGENT_NODES.items():
        g.add_node(name, fn)
    g.add_node("governance", governance)
    g.add_edge(START, "supervisor")
    routes = {name: name for name in AGENT_NODES} | {"governance": "governance"}
    g.add_conditional_edges("supervisor", dispatch, routes)
    for name in AGENT_NODES:
        g.add_conditional_edges(name, dispatch, routes)
    g.add_edge("governance", END)
    return g.compile()


GRAPH = build_graph()


def plan_for(message: str) -> dict[str, Any]:
    s = supervisor({"message": message})  # type: ignore[typeddict-item]
    return {"intent": s["intent"], "plan": s["plan"], "params": s["params"]}


async def run_workflow(user_id: uuid.UUID, message: str, conversation_id: uuid.UUID | None = None, on_event=None) -> CareerState:
    """Run the graph, streaming node-level progress to ``on_event`` and persisting an ``agent_runs`` row."""
    t0 = time.perf_counter()
    with SessionLocal() as db:
        run = AgentRun(user_id=user_id, conversation_id=conversation_id, intent="pending", agents=[], status="running")
        db.add(run)
        db.commit()
        run_id = run.id
    state: CareerState = {"user_id": str(user_id), "run_id": str(run_id), "message": message}
    final: CareerState = dict(state)  # type: ignore[assignment]
    error = None
    try:
        async for update in GRAPH.astream(state, config={"recursion_limit": RECURSION_LIMIT}, stream_mode="updates"):
            for node, delta in update.items():
                if delta:
                    final.update(delta)  # type: ignore[typeddict-item]
                if on_event:
                    await on_event({"type": "agent", "agent": node, "label": AGENT_LABELS.get(node, node),
                                    "plan": final.get("plan", []), "cursor": final.get("cursor", 0)})
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        final["status"] = "failed"
    with SessionLocal() as db:
        run = db.get(AgentRun, run_id)
        run.intent = final.get("intent", "unknown")
        run.agents = final.get("plan", [])
        run.status = final.get("status", "failed")
        run.steps = final.get("steps", [])
        run.error = error
        run.duration_ms = int((time.perf_counter() - t0) * 1000)
        db.commit()
    if error:
        raise RuntimeError(error)
    return final
