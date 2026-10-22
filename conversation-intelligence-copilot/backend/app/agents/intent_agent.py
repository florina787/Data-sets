"""Intent agent: Gemini structured intent with a deterministic fallback and cross-checks."""

from __future__ import annotations

import json

from app.agents.intent_rules import CONV_ID, parse_intent
from app.labeling.taxonomy import TOPICS
from app.llm.gemini_client import LLMUnavailable, get_llm
from app.llm.structured_output import IntentOutput
from app.prompts.registry import get_prompt


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


def resolve_intent(question: str, previous: dict | None, history: list[dict], request_id: str) -> tuple[IntentOutput, str, dict]:
    """Return (intent, source, meta)."""
    prev_cat = previous.get("intent", {}).get("category") if previous else None
    prev_n = len(previous.get("refs", {}).get("ranking", [])[:10]) if previous else None
    rules_intent = parse_intent(question, has_previous=previous is not None, previous_category=prev_cat, previous_top_n=prev_n)
    llm = get_llm()
    if not llm.available():
        return rules_intent, "rules", {"llm_status": llm.status().get("reason")}
    prompt = get_prompt("intent_understanding")
    try:
        res = llm.generate_json(
            prompt,
            prompt.render(taxonomy=", ".join(f"{k} ({v.label})" for k, v in TOPICS.items()),
                          context=json.dumps(compact_context(previous, history), ensure_ascii=False), question=question),
            IntentOutput, request_id=request_id, purpose="intent")
    except LLMUnavailable as e:
        return rules_intent, "rules", {"llm_error": str(e)[:200]}
    intent: IntentOutput = res.parsed  # type: ignore[assignment]
    # Deterministic cross-checks: IDs found by regex are authoritative; follow-up flags need a previous turn.
    ids = [c.upper() for c in CONV_ID.findall(question)]
    if ids and not intent.conversation_ids:
        intent.conversation_ids = ids
    intent.conversation_ids = [c for c in intent.conversation_ids if CONV_ID.fullmatch(c)]
    if previous is None:
        intent.is_follow_up = False
        intent.reference_ranks = []
    meta = {"model": res.model, "tokens": res.usage.total_tokens, "cache_hit": res.cache_hit, "repaired": res.repaired,
            "rules_category": rules_intent.category, "agrees_with_rules": rules_intent.category == intent.category, "retries": res.retries}
    return intent, "gemini", meta
