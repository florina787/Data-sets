"""Conversation orchestration: message -> intent -> governed agent workflow -> dashboard -> recommendations -> validated response.

Every stage event emitted here corresponds to work that actually happened (no simulated progress). Authorization is
never decided here: the persona only shapes presentation, the harness checks agent roles, the tool gateway checks every
tool call against policy for the authenticated principal, and stored conversation context is re-authorized on reuse.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from agents.graph import ask
from backend import runtime as R
from backend.db import models as m
from backend.db.session import session_scope
from conversation import dashboard, personas, recommend
from conversation.intent import CLASSIFIER, INTENTS, classify, describe, perms_of
from conversation.schemas import (KPI, Answer, ApprovalRequirement, Assumption, ChartSpec, Citation, DataFreshness, Discovery, Insight, Intent,
                                  MessageResponse, Node, Table, WorkflowInfo)
from governance import audit, resources
from governance.identity import Principal
from harness.errors import Cancelled, HarnessError, LoadShed
from harness.registry import REGISTRY
from harness.runtime import get_harness
from harness.validation import ungrounded_numbers
from privacy.detect import mask_text
from retrieval.injection import scan_text

STAGES = [("understanding", "Understanding request"), ("permissions", "Checking permissions"), ("evidence", "Retrieving evidence"),
          ("analysis", "Running financial analysis"), ("visualization", "Preparing visualizations"), ("validation", "Validating recommendations")]
ACTIVE: dict[str, tuple[str, threading.Event]] = {}  # request_id -> (owner user id, cancel event)
GLOSSARY = {"AUM": "assets under management - the market value of client assets the firm manages",
            "bps": "basis points - hundredths of a percent (100 bps = 1%)",
            "operating margin": "operating income as a share of revenue",
            "net flows": "new client money minus withdrawals, excluding market movement",
            "revenue yield": "annual fee revenue divided by average AUM"}


class NotFound(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Emitter:
    def __init__(self, fn: Callable[[str, dict], None] | None):
        self.fn, self.stages, self.t0 = fn, [], time.monotonic()

    def __call__(self, event: str, data: dict) -> None:
        if self.fn:
            self.fn(event, data)

    def stage(self, sid: str, status: str, detail: str = "", **extra) -> None:
        label = dict(STAGES)[sid]
        rec = {"id": sid, "label": label, "status": status, "detail": detail, "t_ms": int((time.monotonic() - self.t0) * 1000), **extra}
        self.stages.append(rec)
        self("stage", rec)


# ------------------------------------------------------------------------------------------------ conversations
def _owned(s, principal: Principal, cid: str) -> m.Conversation:
    c = s.get(m.Conversation, cid)
    if c is None or c.tenant_id != principal.tenant_id or c.user_id != principal.user_id or c.archived:
        raise NotFound(cid)  # other users' conversations are indistinguishable from missing ones
    return c


def create_conversation(principal: Principal, persona: str | None) -> dict:
    pid = persona if persona in personas.PERSONAS else personas.default_persona_for(principal.roles)
    with session_scope() as s:
        c = m.Conversation(id=f"CV-{uuid.uuid4().hex[:12]}", tenant_id=principal.tenant_id, user_id=principal.user_id, persona=pid,
                           title="New conversation", state={}, created_at=_now(), updated_at=_now(), archived=False)
        s.add(c)
        out = _conv_dict(c, 0)
    audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action="conversation.create", resource_type="conversation",
                 resource_id=out["id"], decision="allow", details={"persona": pid})
    return out


def _conv_dict(c: m.Conversation, n: int, last: str | None = None) -> dict:
    return {"id": c.id, "persona": c.persona, "title": c.title, "created_at": c.created_at.isoformat(), "updated_at": c.updated_at.isoformat(),
            "message_count": n, "last_intent": (c.state or {}).get("last_intent"), "last_question": last}


def list_conversations(principal: Principal, q: str | None = None, limit: int = 50) -> list[dict]:
    with session_scope() as s:
        stmt = select(m.Conversation).where(m.Conversation.tenant_id == principal.tenant_id, m.Conversation.user_id == principal.user_id,
                                            m.Conversation.archived.is_(False))
        if q:
            like = f"%{q.strip()[:80]}%"
            hits = select(m.ConversationMessage.conversation_id).where(m.ConversationMessage.user_id == principal.user_id,
                                                                       m.ConversationMessage.role == "user", m.ConversationMessage.content.ilike(like))
            stmt = stmt.where(or_(m.Conversation.title.ilike(like), m.Conversation.id.in_(hits)))
        convs = list(s.scalars(stmt.order_by(m.Conversation.updated_at.desc()).limit(min(limit, 100))))
        out = []
        for c in convs:
            msgs = list(s.scalars(select(m.ConversationMessage).where(m.ConversationMessage.conversation_id == c.id, m.ConversationMessage.role == "user")
                                  .order_by(m.ConversationMessage.created_at.desc())))
            out.append(_conv_dict(c, len(msgs), msgs[0].content if msgs else None))
        return out


def recent_questions(principal: Principal, limit: int = 8) -> list[str]:
    with session_scope() as s:
        rows = s.scalars(select(m.ConversationMessage.content).where(m.ConversationMessage.tenant_id == principal.tenant_id,
                                                                     m.ConversationMessage.user_id == principal.user_id,
                                                                     m.ConversationMessage.role == "user")
                         .order_by(m.ConversationMessage.created_at.desc()).limit(40))
        seen, out = set(), []
        for r in rows:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out[:limit]


def update_conversation(principal: Principal, cid: str, persona: str | None = None, title: str | None = None, archived: bool | None = None) -> dict:
    with session_scope() as s:
        c = _owned(s, principal, cid)
        if persona in personas.PERSONAS:
            c.persona = persona
        if title:
            c.title = title[:200]
        if archived:
            c.archived = True
        c.updated_at = _now()
        return _conv_dict(c, 0)


def _reauthorize(principal: Principal, store, refs: dict) -> list[str]:
    """Return the entity refs the principal can no longer read (e.g. a client reassigned since the message was stored)."""
    eng, bad = R.engine(), []
    cid = (refs or {}).get("client_id")
    if cid:
        res = resources.client(store, cid)
        if res is None or not eng.authorize(principal, "client:read", res).allowed:
            bad.append(cid)
    return bad


def get_conversation(principal: Principal, store, cid: str) -> dict:
    with session_scope() as s:
        c = _owned(s, principal, cid)
        msgs = list(s.scalars(select(m.ConversationMessage).where(m.ConversationMessage.conversation_id == cid).order_by(m.ConversationMessage.created_at)))
        out = []
        for x in msgs:
            item = {"id": x.id, "role": x.role, "content": x.content, "status": x.status, "intent": x.intent, "created_at": x.created_at.isoformat(),
                    "request_id": x.request_id}
            if x.role == "assistant":
                revoked = _reauthorize(principal, store, x.entity_refs)
                if revoked:
                    item.update(status="withheld", response=None,
                                content=f"Content withheld: you are no longer authorized to view {', '.join(revoked)}. Ask again to re-run under current permissions.")
                else:
                    item["response"] = x.response
            out.append(item)
        return {**_conv_dict(c, sum(1 for x in msgs if x.role == "user")), "state": {k: v for k, v in (c.state or {}).items() if k != "business_profile"},
                "has_business_profile": bool((c.state or {}).get("business_profile")), "messages": out}


# ------------------------------------------------------------------------------------------------ message processing
def _idempotent(s, cid: str, client_message_id: str | None) -> dict | None:
    if not client_message_id:
        return None
    u = s.scalar(select(m.ConversationMessage).where(m.ConversationMessage.conversation_id == cid,
                                                     m.ConversationMessage.client_message_id == client_message_id))
    if u is None:
        return None
    a = s.scalar(select(m.ConversationMessage).where(m.ConversationMessage.conversation_id == cid, m.ConversationMessage.role == "assistant",
                                                     m.ConversationMessage.request_id == u.request_id))
    return a.response if a and a.response else None


def cancel(request_id: str, principal: Principal | None = None) -> bool:
    """Cancel an in-flight request. Only its owner may cancel it (the stream endpoint cancels its own request on disconnect)."""
    owner_ev = ACTIVE.get(request_id)
    if owner_ev is None or (principal is not None and owner_ev[0] != principal.user_id):
        return False
    owner_ev[1].set()
    get_harness().cancel(request_id)
    return True


def process_message(principal: Principal, store, conversation_id: str, text: str, persona: str | None = None, client_message_id: str | None = None,
                    overrides: dict | None = None, language: str | None = None, emit: Callable[[str, dict], None] | None = None) -> dict:
    em = Emitter(emit)
    with session_scope() as s:
        conv = _owned(s, principal, conversation_id)
        prior = _idempotent(s, conversation_id, client_message_id)
        state = dict(conv.state or {})
        pid = persona if persona in personas.PERSONAS else conv.persona
    if prior is not None:
        em("replay", {"message_id": prior["message_id"]})
        return prior
    request_id = f"WF-{uuid.uuid4().hex[:12]}"
    message_id = f"MSG-{uuid.uuid4().hex[:12]}"
    cancel_ev = threading.Event()
    ACTIVE[request_id] = (principal.user_id, cancel_ev)
    em("started", {"conversation_id": conversation_id, "message_id": message_id, "request_id": request_id})
    try:
        resp, profile = _run(principal, store, conversation_id, message_id, request_id, text, pid, state, overrides or {}, language, em, cancel_ev)
    finally:
        ACTIVE.pop(request_id, None)
    payload = json.loads(MessageResponse.model_validate(resp).model_dump_json())
    _persist(principal, conversation_id, text, client_message_id, payload, state, profile)
    audit.record(tenant_id=principal.tenant_id, actor=principal.user_id, action="conversation.message", resource_type="conversation",
                 resource_id=conversation_id, decision="allow" if payload["status"] in ("complete", "partial", "needs_input") else payload["status"],
                 details={"request_id": request_id, "intent": payload["intent"]["intent"], "persona": pid, "status": payload["status"],
                          "agents": payload["workflow"]["agents"], "question": mask_text(text)[:200]})
    return payload


def _persist(principal: Principal, cid: str, text: str, client_message_id: str | None, payload: dict, state: dict, profile: dict | None) -> None:
    ents = payload["intent"]["entities"]
    new_state = dict(state)
    new_state.update(last_intent=payload["intent"]["intent"], persona=payload["persona"])
    if payload["status"] in ("complete", "partial", "needs_input"):
        for k in ("client_id", "portfolio_id"):
            if ents.get(k) and payload["status"] != "denied":
                new_state[k] = ents[k]
        mods = payload["intent"]["modifiers"]
        if mods.get("months"):
            new_state["months"] = mods["months"]
        if mods.get("scenario"):
            new_state["scenario"] = mods["scenario"]
        if profile:
            new_state["business_profile"] = profile
    with session_scope() as s:
        c = s.get(m.Conversation, cid)
        now = _now()
        try:
            s.add(m.ConversationMessage(id=f"MSG-{uuid.uuid4().hex[:12]}", conversation_id=cid, tenant_id=principal.tenant_id, user_id=principal.user_id,
                                        role="user", content=mask_text(text)[:4000], client_message_id=client_message_id, request_id=payload["request_id"],
                                        status="sent", intent=payload["intent"]["intent"], entity_refs={}, response=None, created_at=now))
            s.add(m.ConversationMessage(id=payload["message_id"], conversation_id=cid, tenant_id=principal.tenant_id, user_id=principal.user_id,
                                        role="assistant", content=payload["answer"]["headline"][:4000], client_message_id=None,
                                        request_id=payload["request_id"], status=payload["status"], intent=payload["intent"]["intent"],
                                        entity_refs={k: ents[k] for k in ("client_id", "portfolio_id") if ents.get(k)},
                                        response=payload, created_at=now))
            if c.title == "New conversation":
                c.title = mask_text(text)[:80]
            c.state, c.persona, c.updated_at = new_state, payload["persona"], now
            s.flush()
        except IntegrityError:
            s.rollback()  # a concurrent duplicate with the same client_message_id already stored the exchange


def _greeting(principal: Principal, persona_id: str, engine) -> tuple[str, list[str], str]:
    p = personas.get(persona_id)
    roles = set(principal.roles)
    can = sorted({REGISTRY.get(a).spec.description.split(":")[0].split(".")[0] for a in REGISTRY.agents
                  if roles & REGISTRY.get(a).spec.allowed_roles and a != "visualization_agent"})[:8]
    head = f"Welcome. I'm FLO, your wealth intelligence workspace - tuned for {p.label}."
    body = ("Ask in plain language and I will route the question to governed specialist agents, compute figures with deterministic analytics, "
            "build the relevant dashboard and recommend next steps. With your current access I can help with: " + "; ".join(can) + ". "
            "All data in this demonstration is synthetic, and actions that affect clients require human approval.")
    return head, list(p.prompts), body


def _run(principal: Principal, store, cid: str, message_id: str, request_id: str, text: str, pid: str, state: dict, overrides: dict,
         language: str | None, em: Emitter, cancel_ev: threading.Event) -> dict:
    eng = R.engine()
    persona = personas.get(pid)
    t0 = time.monotonic()
    created = _now().isoformat() + "Z"
    # 1. understand
    em.stage("understanding", "active")
    plan = classify(text, pid, principal, eng, state, overrides)
    perms = perms_of(principal, eng)
    intent = describe(plan, pid, principal, perms)
    em.stage("understanding", "done", f"{intent['label']} ({CLASSIFIER})")
    em("intent", intent)
    base = dict(conversation_id=cid, message_id=message_id, request_id=request_id, question=text, persona=pid, created_at=created,
                trace_id=request_id)
    inj = scan_text(text)
    # 2. permissions (the identity's real policy decisions; persona plays no part)
    em.stage("permissions", "active")
    use = eng.authorize(principal, "ask:use")
    em.stage("permissions", "done", f"{len(intent['agents_authorized'])} of {len(intent['agents'])} planned agents permitted for your identity",
             authorized=intent["agents_authorized"], not_authorized=intent["agents_not_authorized"])
    if not use.allowed:
        return {**base, "status": "denied", "intent": intent, "answer": Answer(headline="Your identity is not permitted to use FLO conversations.", depth=persona.depth),
                "warnings": ["Policy denied ask:use"], "workflow": WorkflowInfo(stages=em.stages)}, None
    if intent["intent"] in ("greeting", "help"):
        head, prompts, body = _greeting(principal, pid, eng)
        if inj["flagged"]:
            body += " Your message contained text resembling an instruction to bypass controls; it was flagged and ignored."
        return {**base, "status": "complete", "intent": intent, "answer": Answer(headline=head, body=body, depth=persona.depth),
                "suggested_followups": prompts, "workflow": WorkflowInfo(stages=em.stages, injection=inj, latency_ms=int((time.monotonic() - t0) * 1000))}, None
    # 3. governed agent workflow (LangGraph): supervisors -> specialists -> synthesis
    ctx = R.run_context(store, principal, "conversation")
    ctx.workflow_id, ctx.cancel_event = request_id, cancel_ev
    ctx.language = language or "en"
    ctx_ctx: dict[str, Any] = {}
    if intent["intent"] != "general" and intent["agents"]:
        ctx_ctx["route_hint"] = {"domain": INTENTS[intent["intent"]].domain if INTENTS[intent["intent"]].domain in
                                 ("executive", "investment", "wealth", "risk_compliance", "ai_operations") else "executive", "agents": intent["agents"]}
    for k in ("client_id", "portfolio_id"):
        if plan.entities.get(k):
            ctx_ctx[k] = plan.entities[k]
    for k in ("months", "scenario", "business_profile"):
        if plan.modifiers.get(k):
            ctx_ctx[k] = plan.modifiers[k]
    needs_client = INTENTS[intent["intent"]].needs_client and not plan.entities.get("client_id") and bool(intent["agents_authorized"])
    choices: list[dict] = []
    agent_events: list[dict] = []
    em.stage("evidence", "active", "Routing to supervisors and specialist agents")

    def on_event(node: str, upd: dict) -> None:
        if node.endswith("_supervisor") and node != "enterprise_supervisor":
            em("plan", {"supervisor": node, "agents": [p["agent"] for p in upd.get("plan", [])],
                        "skipped": [e["agent"] for e in upd.get("errors", [])]})
        elif node == "specialist":
            for r in upd.get("results", []):
                ev = {"agent": r["agent"], "status": "succeeded", "tools": [t["tool"] for t in ctx.tool_log if t.get("agent") == r["agent"]]}
                agent_events.append(ev)
                em("agent", ev)
            for e in upd.get("errors", []):
                ev = {"agent": e["agent"], "status": "failed", "failure_class": e["failure_class"]}
                agent_events.append(ev)
                em("agent", ev)
        elif node == "synthesize":
            em.stage("evidence", "done", f"{len(ctx.tool_log)} governed tool calls", tool_calls=len(ctx.tool_log))
            em.stage("analysis", "active", "Combining specialist results")

    ans: dict | None = None
    status = "complete"
    try:
        if needs_client:
            em.stage("evidence", "done", "A client identifier is required for this analysis")
            em.stage("analysis", "active")
        else:
            ans = ask(ctx, text, ctx_ctx, language, on_event=on_event)
    except LoadShed:
        raise
    except Cancelled:
        status = "cancelled"
    except HarnessError as e:
        status = "error"
        em("error", {"code": e.code, "message": str(e)[:200]})
    results = (ans or {}).get("results", [])
    errors = (ans or {}).get("errors", [])
    facts = {r["agent"]: r["facts"] for r in results}
    guard_blocked = bool(ans and ans.get("text", "").startswith("Request rejected"))
    em.stage("analysis", "done", f"{len(results)} specialist result(s)")
    # 4. dashboard
    em.stage("visualization", "active")
    charts: list[ChartSpec] = []
    kpis: list[KPI] = []
    withheld: list[dict] = []
    if status not in ("cancelled", "error") and not guard_blocked and (results or needs_client):
        chart_ids = list(intent["charts"])
        for r in results:
            for h in r.get("charts", []):
                h2 = dashboard.ALIASES.get(h, h)
                if h2 and h2 in dashboard.BUILDERS and h2 not in chart_ids and len(chart_ids) < 8 and \
                        dashboard.chart_relevant(h2, perms, bool(principal.advisor_id)):
                    chart_ids.append(h2)
        emph = persona.emphasis
        chart_ids.sort(key=lambda c: emph.index(c) if c in emph else 50)
        kset = INTENTS[intent["intent"]].kpis
        if needs_client:
            chart_ids, kset = ["book_segments"], None
        try:
            out = get_harness().run("visualization_agent", ctx.fork(), {"charts": chart_ids[:8], "kpis": kset, "months": plan.modifiers.get("months", 12),
                                                                         "group_by": plan.modifiers.get("group_by"), "client_id": plan.entities.get("client_id"),
                                                                         "scenario": plan.modifiers.get("scenario") or {},
                                                                         "business_profile": plan.modifiers.get("business_profile") or {}, "persona": pid})
            charts = [ChartSpec.model_validate(c) for c in out.facts["charts"]]
            kpis = [KPI.model_validate(k) for k in out.facts["kpis"]]
            withheld = out.facts["withheld_charts"]
            choices = out.facts.get("client_choices", [])
        except Cancelled:
            status = "cancelled"
        except HarnessError as e:
            withheld.append({"chart_id": "*", "code": e.code})
    em.stage("visualization", "done", f"{len(charts)} chart(s), {len(kpis)} KPI(s)" + (f"; {len(withheld)} withheld by policy" if withheld else ""),
             charts=[c.chart_id for c in charts])
    # 5. recommendations + validation
    em.stage("validation", "active")
    rec = recommend.build(intent["intent"], facts, INTENTS[intent["intent"]].roadmap, persona.owner_functions)
    narrative = (ans or {}).get("text", "")
    headline, summary = _headline(intent, facts, rec, narrative, results)
    all_facts = json.loads(json.dumps({"facts": facts, "kpis": [k.model_dump() for k in kpis]}, default=str))
    bad = ungrounded_numbers(" ".join([headline] + summary), all_facts)
    if bad:  # never show a composed number that is not in the governed facts
        headline, summary = intent["label"], []
    em.stage("validation", "done", f"{len(rec['recommendations'])} recommendation(s), each with cited evidence; numeric grounding "
             + ("passed" if not bad else f"replaced {len(bad)} unverifiable figure(s)"))
    # 6. status, approvals, governance info
    denied_agents = [e for e in errors if e.get("failure_class") in ("not_authorized_or_missing_input", "policy_denied", "admission_rejected")]
    if status == "complete":
        if guard_blocked:
            status = "rejected"
        elif needs_client:
            status = "needs_input"
        elif not results and errors:
            status = "denied" if denied_agents else "error"
        elif errors or withheld:
            status = "partial"
        elif intent["intent"] == "business_onboarding" and not (facts.get("firm_diagnostic_agent") or {}).get("known"):
            status = "needs_input"
    warnings = list((ans or {}).get("warnings", []))
    if intent["agents_not_authorized"]:
        warnings.append("Not permitted for your identity (persona does not change access): " + ", ".join(intent["agents_not_authorized"]))
    warnings += [f"Chart '{w['chart_id']}' withheld ({w['code']})" for w in withheld]
    if inj["flagged"]:
        warnings.append("Instruction-like text in your message was flagged by the injection scanner; tools remain restricted by policy.")
    approvals = _approvals(intent, ans, perms, eng)
    body = narrative if results else ""
    if status == "denied":
        headline = "I can't retrieve that with your current permissions."
        body = ("FLO checked policy for your identity and the requested data is not authorized: "
                + "; ".join(sorted({e['message'] for e in errors}))[:600] + ". Persona selection does not change access.")
    elif status == "needs_input" and needs_client:
        headline = "Which client should I analyse?"
        body = "This analysis needs a client identifier (for example C-00226). Choose one of your clients below or type an ID."
    elif status == "rejected":
        headline = "Request rejected by the input guard."
    elif status == "cancelled":
        headline, body = "Analysis cancelled.", ""
    if persona.depth == "client" and results:
        body += "\n\nTerms: " + "; ".join(f"{k}: {v}" for k, v in GLOSSARY.items() if k.lower() in (body + headline).lower())
    if persona.depth == "analyst" and charts:
        body += "\n\nMethodology: " + " ".join(sorted({c.lineage.methodology for c in charts if c.lineage.methodology}))[:900]
    suggested = rec["followups"] or list(persona.prompts)
    if status in ("denied", "rejected", "error"):
        suggested = list(persona.prompts)
    suggested = [x for x in suggested if x.strip().lower().rstrip(".?!") != text.strip().lower().rstrip(".?!")]
    fdk = (facts.get("firm_diagnostic_agent") or {}).get("known", [])
    if "expenses" in fdk or "advisors" in fdk:
        suggested = [x for x in suggested if not x.startswith("We have ")]
    if needs_client:
        verb = "Build a retirement strategy" if intent["intent"] == "retirement_strategy" else "Prepare a portfolio review"
        suggested = [f"{verb} for {c['client_id']}" for c in choices[:4]] or suggested
    fresh = _freshness(charts, store)
    assumptions = [Assumption(name=a["name"], value=a["value"], unit=a.get("unit", ""), source=a.get("source", "")) for a in
                   (facts.get("scenario_agent", {}).get("assumptions") or []) + ((facts.get("firm_diagnostic_agent") or {}).get("assumptions") or [])]
    discovery = None
    fd = facts.get("firm_diagnostic_agent")
    if fd:
        a = fd["assessment"]
        discovery = Discovery(known=a["known"], missing=a["missing"], questions=a["discovery_questions"], integrations=a["integrations"])
    insights = rec["insights"] + [Insight(id=f"L{i + 1}", section="limitation", title=t) for i, t in enumerate(rec["limitations"])]
    graph = _agent_graph(intent, ans, ctx, agent_events)
    if pid == "ai_ops" or intent["intent"] == "general" and (ans or {}).get("route") == "ai_operations":
        charts.append(graph)
    resp = {**base, "status": status, "intent": Intent(**intent),
            "answer": Answer(headline=headline, summary=summary if status in ("complete", "partial") else [], body=body, depth=persona.depth),
            "insights": insights if status in ("complete", "partial", "needs_input") else [], "kpis": kpis, "charts": charts,
            "tables": dashboard.tables_for(intent["intent"], facts), "recommendations": rec["recommendations"] if status in ("complete", "partial", "needs_input") else [],
            "implementation_plan": rec["plan"] if status in ("complete", "partial", "needs_input") else None,
            "citations": [Citation(**{k: c.get(k, "") for k in ("document_id", "title", "section", "version")}) for c in (ans or {}).get("citations", [])],
            "data_freshness": fresh, "assumptions": assumptions, "warnings": warnings, "approval_requirements": approvals,
            "suggested_followups": suggested[:5], "discovery": discovery, "trace_ids": ctx.trace_ids,
            "workflow": WorkflowInfo(workflow_id=request_id, route=(ans or {}).get("route"), agents=(ans or {}).get("agents", []),
                                     tool_calls=ctx.tool_log, policy_decisions=ctx.policy_log, errors=errors, model=ctx.model.name,
                                     model_mode=(ans or {}).get("model_mode", ""), injection=inj, stages=em.stages,
                                     latency_ms=int((time.monotonic() - t0) * 1000))}
    if needs_client:
        resp["tables"] = [Table(table_id="client_choices", title="Your largest clients with a retirement goal", columns=["Client", "Segment", "Client value (CAD)"],
                                rows=[[x["client_id"], x["segment"], x["client_value"]] for x in choices])] if choices else []
    return MessageResponse.model_validate(resp).model_dump(), plan.modifiers.get("business_profile")


HEADLINE_PREF = {"client_review": ("current_state",), "risk_overview": ("risk",), "scenario": ("finding",), "concentration_risk": ("finding", "risk"),
                 "advisor_productivity": ("finding",), "client_retention": ("current_state",), "retirement_strategy": ("finding",)}


def _headline(intent: dict, facts: dict, rec: dict, narrative: str, results: list) -> tuple[str, list[str]]:
    iid, ins = intent["intent"], rec["insights"]
    a, p, b = facts.get("aum_agent"), facts.get("financial_performance_agent"), facts.get("board_reporting_agent")
    headline = None
    if iid in ("aum_profitability", "firm_overview", "transformation_roadmap") and a and p and p.get("prior_margin_pct") is not None \
            and p["margin_pct"] < p["prior_margin_pct"] and a["aum_growth_pct"] > 0:
        headline = (f"AUM grew {a['aum_growth_pct']}% to CAD {a['aum_bn']}bn while operating margin fell from {p['prior_margin_pct']}% to "
                    f"{p['margin_pct']}%: expenses grew {p['opex_growth_pct']}% against revenue growth of {p['revenue_growth_pct']}%")
    elif iid == "executive_briefing" and b:
        headline = (f"Board summary: AUM CAD {b['aum_bn']}bn ({b['growth_pct']}% over {b['months']} months), operating margin {b['margin_pct']}%"
                    + (f" versus {b['prior_margin_pct']}%" if b.get("prior_margin_pct") is not None else ""))
    elif iid == "business_onboarding" and facts.get("firm_diagnostic_agent"):
        fd = facts["firm_diagnostic_agent"]
        headline = ("Thank you. Here is a preliminary, clearly labelled view of your firm, and what I need to make it precise"
                    if fd["known"] else "Welcome. Tell me a little about your firm and I will build a preliminary view")
    first = None
    if headline is None:
        pref = HEADLINE_PREF.get(iid, ("finding", "current_state"))
        first = next((i for sec in pref for i in ins if i.section == sec), None) or next((i for i in ins if i.section in ("finding", "current_state")), None)
        headline = first.title if first else (narrative.split(". ")[0][:200] if narrative else intent["label"])
    summary = [i.title for i in ins if i.section in ("finding", "risk", "current_state", "opportunity") and i is not first and i.title != headline][:3]
    if rec["recommendations"]:
        summary.append(f"Top recommendation: {rec['recommendations'][0].title}")
    return headline, summary


def _approvals(intent: dict, ans: dict | None, perms: set[str], eng) -> list[ApprovalRequirement]:
    reasons = {"comms:send": "Client communications are sent only after compliance approval of the exact payload.",
               "recommendation:deliver": "Personalized recommendations are delivered only after compliance approval.",
               "board:distribute": "Board materials are distributed only after executive approval.",
               "export:sensitive": "Sensitive exports require privacy approval."}
    spec = eng.bundle.approvals["actions"]
    out = []
    created = {a["action"]: a for a in (ans or {}).get("approvals", []) if isinstance(a, dict) and a.get("action")}
    for act in intent["approval_requirements"]:
        a = created.get(act)
        out.append(ApprovalRequirement(action=act, reason=reasons.get(act, "Approval-gated action."),
                                       approver_roles=list((spec.get(act) or {}).get("approver_roles", [])),
                                       status="pending" if a else ("required" if act in perms else "not_permitted"), approval_id=a["id"] if a else None))
    return out


def _freshness(charts: list[ChartSpec], store) -> DataFreshness:
    lins = [c.lineage for c in charts if c.lineage.as_of]
    return DataFreshness(as_of=max((x.as_of for x in lins), default=None), refreshed_at=max((x.refreshed_at or "" for x in lins), default=None) or None,
                         dataset_version=store.version, synthetic=True, sources=sorted({s for c in charts for s in c.lineage.sources}))


def _agent_graph(intent: dict, ans: dict | None, ctx, agent_events: list[dict]) -> ChartSpec:
    nodes = [Node(id="user", name="Your question", status="ok"), Node(id="enterprise_supervisor", name="Enterprise supervisor", status="ok")]
    edges = [{"source": "user", "target": "enterprise_supervisor"}]
    route = (ans or {}).get("route") or intent["domain"]
    sup = f"{route}_supervisor"
    nodes.append(Node(id=sup, name=sup.replace("_", " ").title(), status="ok"))
    edges.append({"source": "enterprise_supervisor", "target": sup})
    done = {e["agent"]: e for e in agent_events}
    for a in intent["agents"] or (ans or {}).get("agents", []):
        e = done.get(a)
        st = "ok" if e and e["status"] == "succeeded" else "denied" if a in intent["agents_not_authorized"] else "crit" if e else "skipped"
        nodes.append(Node(id=a, name=a.replace("_agent", "").replace("_", " "), status=st, meta={"tools": ", ".join(e.get("tools", [])) if e else ""}))
        edges.append({"source": sup, "target": a})
    nodes.append(Node(id="visualization_agent", name="visualization", status="ok"))
    edges.append({"source": "enterprise_supervisor", "target": "visualization_agent"})
    return ChartSpec(chart_id="agent_workflow", chart_type="agent_graph", title="Agent workflow for this answer",
                     subtitle=f"{len(ctx.tool_log)} governed tool calls · policy decisions logged", nodes=nodes, edges=edges, provenance="workflow_trace",
                     lineage={"sources": ["harness traces"], "methodology": "Nodes and statuses come from this request's workflow events.", "synthetic": True},
                     interactions=["tooltip", "export", "methodology"])
