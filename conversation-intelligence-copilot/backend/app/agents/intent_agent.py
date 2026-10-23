"""Intent agent: resolves a question to a typed intent through the confidence-aware router.

See app/agents/intent_router.py for the stage order (policy -> rules -> semantic -> LLM -> weak
rules -> clarify). This module keeps the (intent, source, meta) contract the graph uses.
"""

from __future__ import annotations

from app.agents.intent_router import route_intent
from app.llm.structured_output import IntentOutput


def compact_context(previous: dict | None, history: list[dict]) -> dict:
    ctx: dict = {"previous_questions": [h["question"][:160] for h in history[-3:]]}
    if previous:
        refs = previous.get("refs", {})
        ctx.update({
            "previous_category": previous.get("intent", {}).get("category"),
            "previous_window": previous.get("scope", {}).get("window", {}).get("label"),
            "previous_ranking": [{"rank": r["rank"], "id": r["key"], "name": r["name"]} for r in refs.get("ranking", [])[:8]],
            "previous_conversation_ids": refs.get("conversation_ids", [])[:5],
        })
    return ctx


SOURCE = {"llm": "llm", "semantic": "semantic"}


def resolve_intent(question: str, previous: dict | None, history: list[dict], request_id: str, allow_llm: bool = True,
                   selected_conversation_id: str | None = None) -> tuple[IntentOutput, str, dict]:
    """Return (intent, source, meta). allow_llm=False is the Zero-LLM path (rules + semantic only)."""
    d = route_intent(question, previous, allow_llm=allow_llm, request_id=request_id, selected_conversation_id=selected_conversation_id)
    return d.intent, SOURCE.get(d.method, "rules"), {"routing": d.meta()}
