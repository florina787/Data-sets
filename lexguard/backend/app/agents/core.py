"""Control-plane agents: Matter Intake, AI Policy, AI Routing, Supervisor.

Each agent's decisions here are deterministic. The Supervisor plans which work agents to call;
it cannot add tools, widen scope or skip gates - those are enforced by the graph and ToolGateway.
"""

from __future__ import annotations

from app.access.matter_access import build_access_scope, check_ethical_wall, check_matter_access
from app.copilot.intent import classify
from app.graph.context import RunContext
from app.matterguard import guard as matterguard
from app.models.domain import sensitivity_rank
from app.providers.registry import ProviderGateway
from app.routing import router, suitability
from app.security.injection import detect_injection
from app.security.tool_gateway import ToolGateway

COC_INTENTS = {"contract_review", "playbook_compare", "escalation_query", "show_evidence"}


def matter_intake(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    user = store.users.get(ctx.user_id)
    matter = store.matters.get(ctx.matter_id) if ctx.matter_id else None
    client = store.clients.get(matter.client_id) if matter else None
    ctx.client_id = client.client_id if client else None
    intent = classify(store, ctx.message, ctx.matter_id)
    destination = ctx.destination_override or intent.destination
    injection = detect_injection(ctx.message)
    out = {
        "user": user.model_dump(mode="json") if user else {"user_id": ctx.user_id},
        "role": user.role.value if user else "UNKNOWN",
        "matter": ({"matter_id": matter.matter_id, "name": matter.name} if matter else {"matter_id": ctx.matter_id}),
        "client": {"client_id": client.client_id} if client else {},
        "task": ctx.message, "intent": intent.intent, "intent_detail": intent.model_dump(),
        "destination": destination, "requested_provider": intent.requested_provider,
        "selected_finding_id": ctx.selected_finding_id, "injection_flags": [], "errors": [],
    }
    ctx.audit("REQUEST_RECEIVED", {"intent": intent.intent, "destination": destination,
                                   "message_chars": len(ctx.message)})
    trace = [{"label": "Request understood", "agent": "matter_intake", "status": "ok",
              "detail": f"Intent: {intent.intent.replace('_', ' ')}"}]
    if injection:
        out["injection_flags"] = [{"source": "user_message", "patterns": injection,
                                   "handling": "Instruction-like text treated as data; permissions unchanged."}]
        ctx.audit("PROMPT_INJECTION_DETECTED", {"source": "user_message", "patterns": injection}, "WARNING")
        trace.append({"label": "Instruction-like text detected in request (treated as data)", "agent": "matter_intake",
                      "status": "warn", "detail": "Cannot change policy, RBAC, ethical walls or tool permissions."})
    out["agent_trace"] = trace
    out["agents_invoked"] = ["matter_intake"]
    return out


def access_control(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    user = store.users.get(ctx.user_id)
    matter = store.matters.get(ctx.matter_id) if ctx.matter_id else None
    dec = check_matter_access(store, user, matter)
    ctx.audit("ACCESS_DECISION", {"allowed": dec.allowed, "code": dec.code, "rule_id": dec.rule_id, "via": dec.via},
              "INFO" if dec.allowed else "WARNING")
    res = {"allowed": dec.allowed, "code": dec.code, "reason": dec.reason, "rule_id": dec.rule_id, "via": dec.via}
    if not dec.allowed:
        ctx.audit("SECURITY_ACCESS_DENIED", {"code": dec.code, "reason": dec.reason, "retrieval_performed": False}, "CRITICAL")
        return {"matter_access": res, "status": "ACCESS_DENIED",
                "agent_trace": [{"label": "Matter access denied", "agent": "access_control", "status": "blocked",
                                 "detail": dec.reason}]}
    return {"matter_access": res,
            "agent_trace": [{"label": "Matter access verified", "agent": "access_control", "status": "ok",
                             "detail": f"{dec.reason} ({dec.rule_id})"}]}


def ethical_wall(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    user = store.users.get(ctx.user_id)
    wall = check_ethical_wall(store, user, ctx.matter_id)
    res = {"blocked": wall.blocked, "wall_id": wall.wall_id, "reason": wall.reason}
    ctx.audit("ETHICAL_WALL_DECISION", res, "CRITICAL" if wall.blocked else "INFO")
    if wall.blocked:
        ctx.audit("SECURITY_ETHICAL_WALL_BLOCK", {"wall_id": wall.wall_id, "retrieval_performed": False}, "CRITICAL")
        return {"ethical_wall_status": res, "status": "ACCESS_DENIED",
                "agent_trace": [{"label": "Ethical wall enforced - access denied before retrieval", "agent": "ethical_wall",
                                 "status": "blocked", "detail": wall.reason}]}
    # Only now - after access + wall - is a sealed retrieval scope created.
    ctx.scope = build_access_scope(store, user, ctx.matter_id)
    return {"ethical_wall_status": res,
            "agent_trace": [{"label": "Ethical wall check passed", "agent": "ethical_wall", "status": "ok",
                             "detail": "No screening applies."}]}


def ai_policy(state: dict, ctx: RunContext) -> dict:
    intent = state["intent"]
    mg = matterguard.evaluate(ctx.store, user_id=ctx.user_id, matter_id=ctx.matter_id,
                              provider_id=state.get("requested_provider"), destination=state.get("destination", "internal"),
                              intent=intent)
    ctx.mg = mg
    ctx.tools = ToolGateway(mg.allowed_tools, int(ctx.cfg.get("max_tool_calls", ctx.settings.max_tool_calls)),
                            lambda e, p, s: ctx.audit(e, p, s))
    ctx.providers = ProviderGateway(mg, lambda e, p, s: ctx.audit(e, p, s))
    ctx.audit("POLICY_DECISION", {"decision": mg.decision, "risk": mg.risk, "rules": [e.rule_id for e in mg.policy_evidence],
                                  "provider_id": mg.provider_id, "provider_permitted": mg.provider_permitted,
                                  "human_review_level": mg.human_review_level}, "INFO" if mg.decision != "PROHIBITED" else "WARNING")
    trace = [{"label": "Client AI policy checked", "agent": "ai_policy", "status": "ok",
              "detail": mg.client_policy_summary}]
    out: dict = {"ai_policy": mg.model_dump(), "risk": mg.risk}
    if not mg.ai_allowed_for_matter:
        trace.append({"label": "AI prohibited for this matter - routed to lawyer / traditional workflow", "agent": "ai_policy",
                      "status": "blocked", "detail": "; ".join(mg.reasons)})
        out["status"] = "HUMAN_ROUTE"
    elif mg.provider_id and not mg.provider_permitted:
        trace.append({"label": "Requested provider blocked by policy", "agent": "ai_policy", "status": "blocked",
                      "detail": "; ".join(mg.reasons)})
        ctx.audit("POLICY_BLOCK", {"provider_id": mg.provider_id, "rules": [e.rule_id for e in mg.policy_evidence if e.effect == "PROHIBIT"],
                                   "reasons": mg.reasons, "alternatives": mg.alternatives}, "WARNING")
        out["status"] = "BLOCKED"
    else:
        trace.append({"label": "AI workflow permitted" + (" with controls" if mg.decision == "PERMITTED_WITH_CONTROLS" else ""),
                      "agent": "ai_policy", "status": "ok" if mg.decision != "RESTRICTED" else "warn",
                      "detail": f"{mg.decision}; {mg.human_review_label}"})
    out["agent_trace"] = trace
    out["agents_invoked"] = ["ai_policy"]
    return out


def assess_suitability(state: dict, ctx: RunContext) -> dict:
    store = ctx.store
    docs = [d for d in store.matter_documents(ctx.matter_id) if d.status == "active"
            and sensitivity_rank(d.sensitivity) <= sensitivity_rank(ctx.scope.max_sensitivity)]
    mg = ctx.mg
    client = store.clients[store.matters[ctx.matter_id].client_id]
    priv_share = (sum(1 for d in docs if d.sensitivity == "privileged") / len(docs)) if docs else 0.0
    provider = store.providers.get(state.get("requested_provider") or "")
    s = suitability.score(intent=state["intent"], doc_count=len(docs), doc_sensitivities=[d.sensitivity for d in docs],
                          privileged_share=priv_share, client_ai_allowed=client.ai_policy.ai_allowed,
                          client_external_allowed=client.ai_policy.external_ai_allowed,
                          external_destination=state.get("destination", "internal").startswith("external"),
                          external_provider=bool(provider and provider.external), human_review_level=mg.human_review_level)
    ctx.audit("SUITABILITY_ASSESSED", s.model_dump(exclude={"factors"}))
    return {"ai_suitability": s.model_dump(),
            "documents": {"active_in_scope": len(docs), "privileged_share": round(priv_share, 3)},
            "agent_trace": [{"label": "AI suitability scored", "agent": "ai_routing", "status": "ok",
                             "detail": f"AI {s.ai_suitability} | agentic {s.agentic_suitability} | legal-judgment risk {s.legal_judgment_risk}"}],
            "agents_invoked": ["ai_routing"]}


PLANS: dict[str, list[str]] = {
    "contract_review": ["document_analysis"],
    "playbook_compare": ["legal_knowledge", "document_analysis"],
    "escalation_query": ["document_analysis"],
    "show_evidence": ["document_analysis"],
    "draft_memo": ["document_analysis", "drafting"],
    "client_draft": ["document_analysis", "drafting"],
    "research": ["legal_research"],
    "knowledge_question": ["legal_knowledge"],
    "summarize": ["document_analysis"],
    "extract_obligations": ["document_analysis"],
    "extract_timeline": ["document_analysis"],
    "extract_entities": ["document_analysis"],
    "compare_documents": ["document_analysis"],
    "citation_verify": ["load_work_product"],
    "recommendation_check": ["load_work_product"],
    "privilege_review": ["privilege_scan"],
    "policy_question": ["policy_explainer"],
    "explain_block": ["policy_explainer"],
    "cross_matter_request": ["policy_explainer"],
    "value_query": ["value_analysis"],
    "legal_judgment": ["legal_research"],
    "external_provider_request": ["document_analysis"],
    "search": ["traditional_search"],
}


def supervisor(state: dict, ctx: RunContext) -> dict:
    intent = state["intent"]
    plan = list(ctx.cfg.get("plan_override") or PLANS.get(intent, ["legal_knowledge"]))
    detail = state.get("intent_detail", {})
    if intent == "compare_documents" and len(detail.get("doc_ids", [])) < 2:
        return {"plan": [], "status": "NEEDS_INPUT",
                "answer": "Please name two documents to compare, e.g. 'Compare MAPLE-C-0012 with MAPLE-C-0013'.",
                "agent_trace": [{"label": "Supervisor needs more input", "agent": "supervisor", "status": "warn",
                                 "detail": "Two document IDs are required for comparison."}],
                "agents_invoked": ["supervisor"]}
    ctx.audit("AGENT_INVOKED", {"agent": "supervisor", "plan": plan, "max_steps": ctx.max_steps})
    return {"plan": plan, "plan_index": 0, "iterations": 0,
            "agent_trace": [{"label": "Supervisor planned workflow", "agent": "supervisor", "status": "ok",
                             "detail": " -> ".join(plan) + f" (max {ctx.max_steps} steps)"}],
            "agents_invoked": ["supervisor"]}


def route(state: dict, ctx: RunContext) -> dict:
    from app.routing.suitability import SuitabilityResult
    suit = SuitabilityResult(**state["ai_suitability"])
    dec = router.recommend(intent=state["intent"], mg=ctx.mg, suit=suit,
                           doc_count=state.get("documents", {}).get("active_in_scope", 0),
                           requested_provider=state.get("requested_provider"))
    ctx.audit("ROUTING_DECISION", {"route": dec.route, "provider_id": dec.provider_id, "workflow_id": dec.workflow_id,
                                   "reasons": dec.reasons})
    out = {"routing_decision": dec.model_dump(), "provider": dec.provider_id, "workflow": dec.workflow_id,
           "agent_trace": [{"label": f"AI Router selected {dec.route.replace('_', ' ').title()}", "agent": "ai_routing",
                            "status": "ok", "detail": dec.reasons[0]}],
           "agents_invoked": ["ai_routing"]}
    if dec.route == "HUMAN_LAWYER" and state["intent"] == "legal_judgment":
        out["status"] = "HUMAN_DECISION_REQUIRED"
    return out
