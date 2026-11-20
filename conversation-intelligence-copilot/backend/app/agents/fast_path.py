"""Conversational fast path: greetings, thanks, "how are you", "what can you do", answered without the agent graph.

Small talk needs no analysis, retrieval or model, so it is answered from templates in well under a millisecond
of logic. Input validation still runs (an injection-flagged message never takes the fast path), and the request
is still recorded: telemetry and audit entries, node events for the trace, and a session-memory turn that
follow-up questions ignore. The templates do not pretend the assistant has feelings or experiences.
"""

from __future__ import annotations

import re
import time
from datetime import UTC, datetime

from app.agents.suggestions import DEFAULT
from app.agents.tracing import NODE_INFO
from app.governance.prompt_injection import sanitize_question, scan

_GREETING = r"(hi|hello|hey|hiya|howdy|greetings|good (morning|afternoon|evening|day))( there| team| all| copilot)?"
_PATTERNS = [
    ("how_are_you", re.compile(rf"^({_GREETING}\s*)?(how are you( doing)?( today)?|how('s| is) it going|how do you do|you ok|are you ok)$")),
    ("greeting", re.compile(rf"^{_GREETING}$")),
    ("thanks", re.compile(r"^(thanks?( you)?( so much| very much| a lot)?|thank you( so much| very much)?|cheers|many thanks|ty|great,? thanks?)$")),
    ("goodbye", re.compile(r"^(bye|goodbye|good ?night|see (you|ya)( later)?|that'?s all( for now)?|talk later)$")),
    ("capabilities", re.compile(r"^(help|what can you do|what do you do|how can you help( me)?|what are you able to do|what can i ask( you)?|"
                                r"what questions can i ask|how do i use (this|you))$")),
    ("identity", re.compile(r"^(who are you|what are you|what is your name|who made you|are you (a bot|an ai|human))$")),
]
CAPABILITIES = ("I analyse the 3,000 customer-support conversations in this dataset. I can rank complaints and the topics most associated "
                "with negative sentiment, show the top positive or negative statements customers wrote, trace how sentiment changed in a "
                "conversation, review empathy and communication signals for coaching, prioritise recurring concerns for leadership, and "
                "find similar conversations. Every number comes from the data and every quote opens its source transcript.")
REPLIES = {
    "greeting": ("Hello! I'm the Conversation Intelligence Copilot.", "What would you like to know about the customer conversations? " + CAPABILITIES),
    "how_are_you": ("I'm running normally and ready to help.", "I'm software, so I don't have feelings, but everything is working. " + CAPABILITIES),
    "thanks": ("You're welcome.", "Ask a follow-up whenever you like; I keep the context of this session."),
    "goodbye": ("Goodbye!", "Your session is saved, so you can pick up where you left off."),
    "capabilities": ("Here's what I can do.", CAPABILITIES),
    "identity": ("I'm the Conversation Intelligence Copilot, an AI analytics assistant.",
                 "I'm software, not a person. " + CAPABILITIES + " A local language model helps only with questions that need interpretation."),
}


def classify(question: str) -> str | None:
    text = re.sub(r"[^a-z' ]+", " ", question.lower()).strip()
    text = re.sub(r"\s+", " ", text)
    if not text or len(text) > 60:
        return None
    for kind, pat in _PATTERNS:
        if pat.match(text):
            return kind
    return None


def respond(question: str, request_id: str, session_id: str, dataset_mode: str) -> tuple[dict, list[dict]] | None:
    """(response, node events) for small talk, or None when the question needs the agent graph."""
    t0 = time.perf_counter()
    started = datetime.now(UTC).isoformat()
    q = sanitize_question(question or "")
    if not q or scan(q):
        return None
    kind = classify(q)
    if kind is None:
        return None
    from app.config import get_settings
    from app.llm.gemini_client import get_llm
    from app.schemas.analysis import Scope
    from app.schemas.api_response import ChatResponse

    headline, answer = REPLIES[kind]
    ms = round((time.perf_counter() - t0) * 1000, 2)
    events = []
    for node, summary in (("input_validation", {"chars": len(q), "injection_flags": 0}),
                          ("router", {"route": "fast_path", "kind": kind})):
        ev = {"node": node, "label": NODE_INFO[node]["label"], "status": "completed", "started_at": started,
              "finished_at": datetime.now(UTC).isoformat(), "duration_ms": ms, "retries": 0, "input_summary": {},
              "output_summary": summary, "error": None, "meta": {}}
        events.append(ev)
    st = get_llm().status()
    routing = {"requested_mode": "auto", "route": "fast_path", "llm_available": st.get("available"), "llm_steps": [], "rules_category": "general_chat",
               "reason": f"Small talk ('{kind.replace('_', ' ')}') answered from a template: no agents, analysis or model were needed."}
    resp = ChatResponse(
        version="1.0", request_id=request_id, session_id=session_id, status="completed", question=q,
        resolved_intent={"category": "general_chat", "kind": kind}, dataset_scope=Scope(dataset_mode=dataset_mode).model_dump(),
        plan={"category": "general_chat", "specialist": None, "steps": [], "retrieval": {"mode": "none"}, "notes": [], "resolved_references": {},
              "audience": "analyst"},
        headline=headline, answer=answer, follow_up_questions=list(DEFAULT), execution_trace_id=request_id,
        model_metadata={"provider": st.get("provider"), "model": st.get("model"), "mode": "deterministic", "available": st.get("available"),
                        "intent_source": "fast_path", "explanation_source": "template", "label_source": get_settings().label_source, "routing": routing},
        routing=routing, token_usage={"model_calls": 0, "total_tokens": 0, "input_tokens": 0, "output_tokens": 0, "cache_hits": 0, "unreported_calls": 0},
        quality_status={"status": "pass", "passed": 2, "total": 2, "checks": [
            {"check": "input_validated", "passed": True, "critical": True, "detail": "No injection patterns; question within limits"},
            {"check": "no_data_claims", "passed": True, "critical": True, "detail": "Conversational reply; no figures or findings are claimed"}]},
        groundedness={"basis": "no_analysis", "score": None, "risk": "low", "label": "Conversation (no analysis)",
                      "reasons": ["Template reply to small talk; no data or model was used."], "components": {}},
    )
    return resp.model_dump(), events
