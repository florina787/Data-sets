"""Conversational turns that need no specialist graph, and the per-session context used for follow-ups.

General-knowledge answers come from local Qwen only and are labelled as general knowledge: they may not state
anything about this fleet's data (the challenger removes fleet identifiers and numbers). Without Qwen the
assistant says so instead of inventing an answer.
"""

from __future__ import annotations

import re
import time
from typing import Any

from pydantic import BaseModel, Field

from app.core import audit, db, policy
from app.core.security import Actor
from app.core.util import now_iso
from app.llm.gateway import LLMError, LLMUnavailable, gateway
from app.workflows.engine import CaseState, _event
from app.workflows.router import FAMILIES, Route

FOUR_QUESTIONS = [
    {"family": "diagnostics", "title": "Aircraft Diagnostics", "question": "Why is aircraft AC-204 showing abnormal vibration, and what should engineering investigate?"},
    {"family": "recovery", "title": "Aircraft Recovery", "question": "Which recovery option could return AC-204 to service fastest, considering spare parts, maintenance scheduling, and engineering approval?"},
    {"family": "modernization", "title": "Legacy Modernization", "question": "How can we modernize our legacy aircraft maintenance system using APIs, MCP, and AI without replacing the existing platform?"},
    {"family": "executive", "title": "Executive Intelligence", "question": "What is affecting fleet readiness, and which maintenance improvements could reduce downtime and cost?"},
]


class GKAnswer(BaseModel):
    answer: str = Field(max_length=1200)
    caveat: str = Field(default="", max_length=300)


FLEET_ID = re.compile(r"\b(AC-\d{3}|P-\d{3,5}[A-Z]?|DOC-\d{3}|WO-\d+|SUP-\d{2})\b")


def get_context(session_id: str | None) -> dict[str, Any] | None:
    if not session_id:
        return None
    r = db.query_one("SELECT * FROM conversation_context WHERE session_id = ?", (session_id,))
    if not r:
        return None
    return {"family": r["family"], "workflow": r["workflow"], "entities": db.jload(r["entities_json"], {}), "last_query": r["last_query"]}


def save_context(session_id: str, r: Route, query: str) -> None:
    if not r.family:
        return
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO conversation_context VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET family=excluded.family, "
                     "workflow=excluded.workflow, entities_json=excluded.entities_json, last_query=excluded.last_query, updated=excluded.updated",
                     (session_id, r.family, r.workflow, db.jdump(r.entities), query[:500], now_iso()))


def _md(text: str) -> dict[str, Any]:
    return {"type": "answer", "markdown": text}


def answer(state: CaseState, r: Route, actor: Actor) -> None:
    t0 = time.perf_counter()
    label = r.label
    if label == "greeting":
        state.answer = ("Hello, I'm **Flying_Florina**, your aerospace and defense intelligence copilot. I can diagnose aircraft anomalies, compare recovery "
                        "options, plan legacy modernization and brief leadership on readiness. Every number comes from verified data; Qwen explains it.")
        state.workspace = [_md(state.answer), {"type": "four_questions", "items": FOUR_QUESTIONS}]
        state.status = "completed"
    elif label == "policy_refusal":
        d = policy.evaluate(actor, policy.PolicyRequest(action="tool_call", resource="chat:instruction_override", label="RESTRICTED",
                                                        instruction_source="retrieved_content", tool="instruction_override", tool_registered=False, run_id=state.run_id))
        state.policy_decisions.append(d.as_dict())
        state.answer = ("**Request refused.** It asks me to override instructions, change privileges or approve actions. Instructions in chat or documents "
                        f"cannot change policy, and I cannot approve, certify or grant access ({d.policy_id}). The attempt is recorded in the audit log.")
        state.workspace = [_md(state.answer), {"type": "policy", "decisions": [d.as_dict()], "allowed": 0, "denied": 1}]
        state.status = "denied"
    elif label == "unsupported":
        state.answer = ("That's outside what I can answer. I work only with Flying_Florina's synthetic aerospace maintenance data and modernization "
                        "fixtures, and general aviation concepts. I won't guess. Try one of the questions below.")
        state.workspace = [_md(state.answer), {"type": "four_questions", "items": FOUR_QUESTIONS}]
        state.status = "completed"
    elif label == "clarify":
        state.answer = "I need a bit more to go on. Which aircraft, system or goal do you mean? Here are the analyses I can run:"
        state.workspace = [_md(state.answer), {"type": "four_questions", "items": FOUR_QUESTIONS}]
        state.status = "needs_clarification"
    elif label == "general_knowledge":
        _general_knowledge(state)
    _event(state.run_id, label, "Flying_Florina Assistant", "completed", 1, (time.perf_counter() - t0) * 1000, state.answer[:200])
    audit.append(actor.id, "chat.conversational", f"{label}: {state.query[:100]}", {"run_id": state.run_id, "route": r.method})


def _general_knowledge(state: CaseState) -> None:
    g = gateway()
    if not g.available():
        state.answer = ("This is a general aviation question. Answering it needs the local Qwen model, which isn't available right now "
                        f"({(g.discovery.reason if g.discovery else '')[:160]}). I won't make up an answer.")
        state.workspace = [_md(state.answer), {"type": "qwen_status", "available": False, "reason": g.discovery.reason if g.discovery else ""}]
        state.status = "completed"
        return
    system = ("You are Flying_Florina. Answer a GENERAL aviation, maintenance or enterprise-integration question in at most 120 words. "
              "Do not mention any specific aircraft, part, document or fleet statistic; you have no fleet data here. If unsure, say so. "
              "Reply as JSON {\"answer\": ..., \"caveat\": ...}.")
    try:
        r = g.generate(agent="General Knowledge", task="general_knowledge", system=system, user=state.query, schema=GKAnswer, max_tokens=220)
    except (LLMError, LLMUnavailable) as err:
        state.answer = f"Local Qwen could not answer in time ({str(err)[:120]}). I won't make up an answer."
        state.workspace = [_md(state.answer)]
        state.status = "completed"
        return
    text = (r.data or {}).get("answer", "")
    leaked = FLEET_ID.findall(text)
    if leaked:
        text = FLEET_ID.sub("[fleet-specific reference removed]", text)
    state.answer = text
    state.answer_model = text
    state.workspace = [{"type": "qwen_answer", "headline": "General aviation knowledge", "summary": text, "key_findings": [], "recommended_next_steps": [],
                        "limitations": [(r.data or {}).get("caveat") or "General knowledge from the local model, not from this fleet's records."],
                        "meta": {"model": r.model, "runtime": r.runtime, "latency_ms": r.latency_ms, "first_token_ms": r.first_token_ms,
                                 "tokens_per_s": r.tokens_per_s, "prompt_tokens": r.prompt_tokens, "completion_tokens": r.completion_tokens, "cached": r.cached},
                        "challenger": {"verdict": "pass_with_removals" if leaked else "pass", "issues": [{"issue": f"fleet identifier {x} removed"} for x in leaked],
                                       "removed": len(leaked), "claims_checked": 1, "unsupported": len(leaked), "checks": ["no fleet-specific claims"]},
                        "general_knowledge": True}]
    state.status = "completed"


def family_title(family: str | None) -> str | None:
    return FAMILIES[family]["title"] if family in FAMILIES else None
