"""Florome Assistant: one conversation engine, specialised per page by configuration.

Routing is deterministic: exact match on a known question, then keyword scoring within the current page's intents,
then across all pages, then conversation memory for vague follow-ups ("why?", "show me more"). No language model is
involved, so answers are reproducible and grounded; anything outside the known intents gets an explicit
"can't answer from Florome data" reply instead of a guess.
"""

from __future__ import annotations

import inspect
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from florome.assistant import answers as h
from florome.assistant.models import AssistantConversation, AssistantMessage
from florome.context import AppContext
from florome.models import Tenant
from florome.security.injection import sanitize, scan
from florome.security.rbac import Principal
from florome.security.redaction import redact

ENGINE = {"name": "florome-assistant", "mode": "rule-based, grounded in Florome data", "language_model": None}
MAX_QUESTION = 500

# intent -> (handler, canonical question, keywords)
INTENTS: dict[str, tuple[Any, str, list[str]]] = {
    "incidents_open": (h.incidents_open, "What's broken right now?", ["broken", "open incident", "incidents", "outage", "down"]),
    "approvals_pending": (h.approvals_pending, "What needs my approval?", ["approval", "approve", "waiting", "pending", "sign off"]),
    "connections_health": (h.connections_health, "How healthy are our connections?", ["connection", "connected", "health check", "integrations"]),
    "spend_month": (h.spend_month, "What did we spend last month?", ["spend", "spent", "cost", "bill", "last month"]),
    "failing_systems": (h.failing_systems, "Which systems are failing?", ["failing", "unhealthy", "red", "which systems", "status"]),
    "upstream": (h.upstream, "What's upstream of the failing service?", ["upstream", "feeds", "depends", "dependency", "dependencies"]),
    "blast_radius": (h.blast_radius, "What is the blast radius?", ["blast", "impact", "affected", "radius", "business"]),
    "health_by_platform": (h.health_by_platform, "Which cloud has the most failures?", ["which cloud", "per cloud", "by platform", "clouds", "most failures"]),
    "root_cause": (h.root_cause, "What caused the incident?", ["cause", "caused", "root", "why did", "reason", "culprit"]),
    "ruled_out": (h.ruled_out, "Which explanations were ruled out?", ["ruled out", "disproven", "red herring", "excluded", "not the cause"]),
    "weakest": (h.weakest, "Where is the evidence weakest?", ["weak", "caveat", "uncertain", "confidence", "gaps", "challenger"]),
    "timeline": (h.timeline, "Show the timeline of events", ["timeline", "when", "sequence", "order of events", "history"]),
    "plan_changes": (h.plan_changes, "What will the plan change?", ["plan", "steps", "change", "remediation", "repair"]),
    "who_approves": (h.who_approves, "Who still needs to approve?", ["who", "approver", "approved by", "sign"]),
    "fix_worked": (h.fix_worked, "Did the fix work?", ["work", "recovered", "recovery", "validated", "fixed", "resolved"]),
    "failures_denied": (h.failures_denied, "What failed or was denied?", ["failed", "failure", "denied", "error in action", "refused"]),
    "really_connected": (h.connections_health, "Which platforms are really connected?", ["really connected", "real", "verified"]),
    "mcp_tools": (h.mcp_tools, "What can the MCP tools do?", ["mcp", "tools", "tool"]),
    "quarantined": (h.quarantined, "Which tools are quarantined?", ["quarantine", "disabled", "blocked tool", "suspicious"]),
    "planned": (h.planned, "What's planned next?", ["planned", "roadmap", "next", "not built", "coming"]),
    "evidence_sources": (h.evidence_sources, "Where does the evidence come from?", ["evidence", "source", "sources", "kinds of evidence", "records"]),
    "evidence_integrity": (h.evidence_integrity, "Has any evidence been tampered with?", ["tamper", "integrity", "altered", "hash", "fingerprint"]),
    "log_gaps": (h.log_gaps, "Which systems have no logs?", ["no logs", "silent", "missing logs", "coverage", "blind spot"]),
    "latest_errors": (h.latest_errors, "Show the latest errors", ["latest error", "errors", "logs", "exceptions"]),
    "audit_intact": (h.audit_intact, "Is the audit log intact?", ["audit", "log intact", "chain", "trail"]),
    "denied_recent": (h.denied_recent, "What was denied recently?", ["denied recently", "blocked", "rejected", "refusals"]),
    "policy_current": (h.policy_current, "What's the current policy?", ["policy", "rules", "mode", "emergency stop", "autonomous"]),
    "api_speed": (h.api_speed, "How fast is the API?", ["fast", "latency", "speed", "slow", "performance", "response time"]),
    "spend_where": (h.spend_where, "Where does the money go?", ["money", "where does", "business unit", "breakdown"]),
    "spend_change": (h.spend_change, "What changed month on month?", ["month on month", "trend", "increase", "growth", "compare"]),
    "spend_ai": (h.spend_ai, "Which AI component costs most?", ["ai component", "model cost", "agent cost", "most expensive ai"]),
    "spend_outcome": (h.spend_outcome, "Which business outcome costs most?", ["outcome", "business outcome", "value"]),
    "vulns_confirmed": (h.vulns_confirmed, "Which vulnerabilities are confirmed?", ["vulnerab", "confirmed", "security hole", "exploit", "findings"]),
    "false_alarms": (h.false_alarms, "Which alarms were false?", ["false", "alarm", "false positive", "decoy", "not real"]),
    "fixes_verified": (h.fixes_verified, "Were the fixes verified?", ["fix", "patch", "retest", "regression"]),
    "agents": (h.agents, "Did any AI agent misbehave?", ["agent", "misbehave", "rogue", "containment", "contained"]),
    "proving": (h.proving, "Does proving beat guessing?", ["proving", "benchmark", "evaluation", "precision", "recall", "compare approaches"]),
    "finding_detail": (h.finding_detail, "Explain the selected finding", ["selected", "this finding", "explain this", "this one"]),
    "code_reach": (h.code_reach, "Which public endpoints reach dangerous code?", ["endpoint", "public", "reach", "graph", "unauthenticated"]),
}

PAGES: dict[str, dict[str, Any]] = {
    "overview": {"title": "Overview", "intents": ["incidents_open", "approvals_pending", "connections_health", "spend_month"]},
    "topology": {"title": "Nervous System", "intents": ["failing_systems", "upstream", "blast_radius", "health_by_platform"]},
    "rca": {"title": "RCA", "intents": ["root_cause", "ruled_out", "weakest", "timeline"]},
    "actions": {"title": "Actions", "intents": ["plan_changes", "who_approves", "fix_worked", "failures_denied"]},
    "integrations": {"title": "Integrations", "intents": ["really_connected", "mcp_tools", "quarantined", "planned"]},
    "sources": {"title": "Sources", "intents": ["evidence_sources", "evidence_integrity", "log_gaps", "latest_errors"]},
    "governance": {"title": "Governance", "intents": ["audit_intact", "denied_recent", "policy_current", "api_speed"]},
    "finops": {"title": "FinOps", "intents": ["spend_where", "spend_change", "spend_ai", "spend_outcome"]},
    "shield": {"title": "Shield", "intents": ["vulns_confirmed", "false_alarms", "fixes_verified", "agents"]},
}
BY_QUESTION = {q.lower(): k for k, (_, q, _) in INTENTS.items()}
VAGUE = re.compile(r"^\s*(why|how|explain|more|tell me more|show me|details?|go on|and\??|what else)\b", re.I)
# Only an explicit request produces a report: "why did the revenue report break?" is a question, not a request.
REPORT = re.compile(r"\b(summari[sz]e|brief me)\b|\b(generate|write|create|make|give me|export)\b.{0,30}\b(report|summary|brief)\b", re.I)


def page_config(page: str) -> dict[str, Any]:
    cfg = PAGES.get(page)
    if cfg is None:
        raise KeyError(page)
    return {"page": page, "title": cfg["title"], "starters": [INTENTS[i][1] for i in cfg["intents"]], "engine": ENGINE}


def route(page: str, question: str, last_intent: str | None, focus: dict[str, Any]) -> str | None:
    q = question.strip().lower().rstrip("?") + ("?" if question.strip().endswith("?") else "")
    if q in BY_QUESTION:
        return BY_QUESTION[q]
    if q.rstrip("?") in {k.rstrip("?") for k in BY_QUESTION}:
        return next(v for k, v in BY_QUESTION.items() if k.rstrip("?") == q.rstrip("?"))
    if focus.get("hypothesis_id") and re.search(r"\b(this|selected)\b", q):
        return "finding_detail"

    def score(intent: str) -> int:
        return sum(len(k) for k in INTENTS[intent][2] if k in q)

    local = sorted(((score(i), i) for i in PAGES.get(page, {}).get("intents", [])), reverse=True)
    if local and local[0][0] > 0:
        best_global = max(((score(i), i) for i in INTENTS), default=(0, None))
        return local[0][1] if local[0][0] >= best_global[0] else best_global[1]
    best = max(((score(i), i) for i in INTENTS), default=(0, None))
    if best[0] > 0:
        return best[1]
    if last_intent and VAGUE.search(q):
        return last_intent
    return None


async def answer(db: Session, app: AppContext, p: Principal, page: str, question: str, conversation_id: str | None,
                 context: dict[str, Any], request_samples: list) -> tuple[AssistantConversation, dict[str, Any]]:
    if page not in PAGES:
        raise KeyError(page)
    q = sanitize(question, MAX_QUESTION)
    conv = None
    if conversation_id:
        conv = db.get(AssistantConversation, conversation_id)
        if conv is None or conv.tenant_id != p.tenant_id or conv.user_id != p.user_id:
            raise LookupError("conversation not found")
    if conv is None:
        conv = AssistantConversation(tenant_id=p.tenant_id, user_id=p.user_id, page=page, focus={})
        db.add(conv)
        db.flush()
    focus = {**conv.focus, **{k: v for k, v in context.items() if k in ("incident_id", "hypothesis_id") and isinstance(v, str) and v}}
    flags = scan(q)  # flagged text is still treated purely as a question; nothing in it is executed or obeyed
    ctx = h.Ctx(db, app, p, focus, list(request_samples))

    if REPORT.search(q):
        intent = "page_report"
        parts = []
        for i in PAGES[page]["intents"]:
            fn = INTENTS[i][0]
            res = await fn(ctx) if inspect.iscoroutinefunction(fn) else fn(ctx)
            parts.append((INTENTS[i][1], res))
        md = f"# Florome · {PAGES[page]['title']} brief\n\n" + "\n".join(f"**{qq}**\n- {r['statement']}\n" + "".join(f"  - {b}\n" for b in r["bullets"][:3])
                                                                       for qq, r in parts)
        ans = h.A(f"Here is a {len(parts)}-point brief of the {PAGES[page]['title']} page.", [r["statement"] for _, r in parts],
                  {"type": "report", "markdown": md}, follow=[INTENTS[i][1] for i in PAGES[page]["intents"]])
    else:
        intent = route(page, q, focus.get("last_intent"), focus)
        if intent is None:
            ans = h.A("I can't answer that from Florome's data; here is what I can answer on this page.",
                      ["Answers are rule-based and grounded in recorded data: no AI model is configured, so I don't guess."],
                      follow=[INTENTS[i][1] for i in PAGES[page]["intents"]])
        else:
            fn = INTENTS[intent][0]
            ans = await fn(ctx) if inspect.iscoroutinefunction(fn) else fn(ctx)
    new_focus = {**focus, **{k: v for k, v in ans.pop("focus", {}).items() if v}}
    if intent:
        new_focus["last_intent"] = intent if intent != "page_report" else focus.get("last_intent")
    conv.focus = new_focus
    ans = redact({**ans, "intent": intent, "engine": ENGINE, "input_flags": flags,
                  "data_mode": db.get(Tenant, p.tenant_id).mode})
    db.add(AssistantMessage(tenant_id=p.tenant_id, conversation_id=conv.id, role="user", text=redact(q)))
    db.add(AssistantMessage(tenant_id=p.tenant_id, conversation_id=conv.id, role="assistant", text=ans["statement"], answer=ans))
    db.flush()
    return conv, ans


def history(db: Session, p: Principal, conversation_id: str) -> list[dict[str, Any]]:
    conv = db.get(AssistantConversation, conversation_id)
    if conv is None or conv.tenant_id != p.tenant_id or conv.user_id != p.user_id:
        raise LookupError("conversation not found")
    rows = db.scalars(select(AssistantMessage).where(AssistantMessage.conversation_id == conv.id).order_by(AssistantMessage.created_at)).all()
    return [{"role": m.role, "text": m.text, "answer": m.answer} for m in rows]
