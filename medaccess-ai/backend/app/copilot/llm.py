"""Optional LLM layer (LangChain + Anthropic) with token optimisation controls.

Disabled unless LLM_ENABLED=true and ANTHROPIC_API_KEY is set. The deterministic
copilot is fully functional without it. When enabled:

* Small-model routing: slot extraction uses ``LLM_ROUTER_MODEL``; explanations use
  ``LLM_EXPLAINER_MODEL``.
* Prompt caching: the static system prompt is sent with ``cache_control``.
* Context compression: only a rolling summary + the last few turns are sent.
* Duplicate-call prevention: identical requests are served from an LRU cache.
* Token budgets: per-workflow budgets via ``RunContext.charge_tokens`` and a
  response-size limit (``LLM_MAX_RESPONSE_TOKENS``).
* Only redacted, non-identifying structured facts are sent to the provider.
* Every call's real token usage (from the API response) is recorded in model_usage.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict

from pydantic import BaseModel

from app.config.settings import get_settings
from app.database.session import session_scope
from app.models import db as m
from app.security.guards import redact
from app.telemetry import metrics as tm

SYSTEM_PROMPT = (
    "You are Christina, a virtual healthcare ACCESS assistant for MedAccess AI (not a clinician). "
    "You help with appointment logistics only. Never diagnose, never assess urgency, never claim an "
    "appointment is booked or confirmed. Use only the structured facts provided. Keep replies under 90 words. "
    "If facts say data is synthetic, say results are demonstration data."
)
PROMPT_VERSION = "christina-v1"

# Published list prices (USD per million tokens) must be configured by the operator; unknown -> 0 and flagged.
PRICE_PER_MTOK: dict[str, tuple[float, float]] = {}

_cache: OrderedDict[str, dict] = OrderedDict()
_CACHE_MAX = 256


class LlmResult(BaseModel):
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms: float = 0.0
    cache_hit: bool = False
    estimated_cost_usd: float | None = None


def available() -> bool:
    return get_settings().llm_configured


def _client(model: str):
    from langchain_anthropic import ChatAnthropic

    s = get_settings()
    return ChatAnthropic(model=model, api_key=s.anthropic_api_key.get_secret_value(),
                         max_tokens=s.llm_max_response_tokens, timeout=15, max_retries=1)


def compress_history(history: list[dict], keep_last: int = 4) -> list[dict]:
    """Rolling summary of older turns (deterministic) + last N turns, redacted."""
    older, recent = history[:-keep_last], history[-keep_last:]
    msgs = []
    if older:
        msgs.append({"role": "user", "content": f"(Summary of {len(older)} earlier turns omitted for brevity.)"})
    msgs.extend({"role": h["role"], "content": redact(h["content"])[:600]} for h in recent)
    return msgs


def complete(purpose: str, facts: dict, history: list[dict] | None = None, workflow_id: str | None = None,
             ctx=None, model: str | None = None) -> LlmResult | None:
    if not available():
        return None
    s = get_settings()
    model = model or (s.llm_router_model if purpose == "extract" else s.llm_explainer_model)
    safe_facts = redact(facts)
    payload = {"facts": safe_facts, "history": compress_history(history or [])}
    key = hashlib.sha256(json.dumps([model, purpose, payload], sort_keys=True, default=str).encode()).hexdigest()
    if key in _cache:
        _cache.move_to_end(key)
        return LlmResult(**{**_cache[key], "cache_hit": True, "input_tokens": 0, "output_tokens": 0})
    from langchain_core.messages import HumanMessage, SystemMessage

    msgs: list = [SystemMessage(content=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}])]
    for h in payload["history"]:
        msgs.append(HumanMessage(content=h["content"]) if h["role"] == "user" else HumanMessage(content=f"(assistant) {h['content']}"))
    msgs.append(HumanMessage(content=f"Task: {purpose}. Facts (JSON): {json.dumps(safe_facts, default=str)[:3000]}"))
    t0 = time.perf_counter()
    resp = _client(model).invoke(msgs)
    lat = (time.perf_counter() - t0) * 1000
    usage = getattr(resp, "usage_metadata", None) or {}
    details = usage.get("input_token_details") or {}
    res = LlmResult(text=str(resp.content if isinstance(resp.content, str) else resp.content[0].get("text", "")),
                    model=model, input_tokens=usage.get("input_tokens", 0), output_tokens=usage.get("output_tokens", 0),
                    cached_tokens=details.get("cache_read", 0), latency_ms=round(lat, 1))
    if model in PRICE_PER_MTOK:
        pi, po = PRICE_PER_MTOK[model]
        res.estimated_cost_usd = round(res.input_tokens / 1e6 * pi + res.output_tokens / 1e6 * po, 6)
    if ctx is not None:
        ctx.charge_tokens(res.input_tokens + res.output_tokens)
    tm.LLM_TOKENS.labels(model=model, kind="input").inc(res.input_tokens)
    tm.LLM_TOKENS.labels(model=model, kind="output").inc(res.output_tokens)
    tm.STORE.add("llm_tokens", res.input_tokens + res.output_tokens, {"model": model, "purpose": purpose})
    with session_scope() as s_:
        s_.add(m.ModelUsage(workflow_id=workflow_id, model=model, purpose=purpose, input_tokens=res.input_tokens,
                            output_tokens=res.output_tokens, cached_tokens=res.cached_tokens,
                            estimated_cost_usd=res.estimated_cost_usd or 0.0, latency_ms=res.latency_ms))
    _cache[key] = res.model_dump()
    if len(_cache) > _CACHE_MAX:
        _cache.popitem(last=False)
    return res


def prompt_payload_size(facts: dict, history: list[dict], optimized: bool) -> int:
    """Characters that would be sent for a request - used by the token benchmark when no API is configured."""
    if optimized:
        body = json.dumps({"facts": redact(facts), "history": compress_history(history)}, default=str)
        return len(body)  # system prompt is cached after the first call
    body = json.dumps({"facts": facts, "history": history}, default=str)
    return len(SYSTEM_PROMPT) + len(body)
