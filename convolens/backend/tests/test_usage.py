"""Streamed token usage: no double counting, whatever shape the provider reports it in."""
import json

import pytest
from langchain_core.messages import AIMessageChunk

from app.config import get_settings
from app.graph import nodes
from app.llm.provider import set_model_override
from app.llm.usage import StreamUsage
from tests.fakes import ScriptedModel


def _u(i, o, **extra):
    return {"input_tokens": i, "output_tokens": o, "total_tokens": i + o, **extra}


def _collect(usages):
    s = StreamUsage()
    for u in usages:
        s.add(AIMessageChunk(content="x", usage_metadata=u) if u else AIMessageChunk(content="x"))
    return s.totals()


def test_cumulative_usage_on_every_chunk_is_not_summed():
    # Shape measured live from Gemini's OpenAI-compatible stream on 22 Oct 2026.
    t = _collect([_u(8, 14), _u(8, 38), _u(8, 41), _u(8, 41), None])
    assert (t["input_tokens"], t["output_tokens"], t["mode"]) == (8, 41, "cumulative")


def test_final_chunk_only():
    t = _collect([None, None, _u(120, 30)])
    assert (t["input_tokens"], t["output_tokens"], t["mode"]) == (120, 30, "final_only")


def test_incremental_usage_is_summed():
    # Prompt reported once, then per-chunk output deltas (Anthropic-style).
    t = _collect([_u(500, 1), _u(0, 12), _u(0, 9)])
    assert (t["input_tokens"], t["output_tokens"], t["mode"]) == (500, 22, "incremental")


def test_missing_usage_is_reported_not_estimated():
    t = _collect([None, None])
    assert t == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "mode": "missing", "details": {}}


def test_empty_stream():
    assert StreamUsage().totals()["mode"] == "missing"


def test_reasoning_and_cache_details_kept_from_final_cumulative_report():
    t = _collect([_u(50, 5, output_token_details={"reasoning": 2}), _u(50, 20, input_token_details={"cache_read": 40},
                                                                         output_token_details={"reasoning": 9})])
    assert t["details"] == {"input_token_details": {"cache_read": 40}, "output_token_details": {"reasoning": 9}}


class CumulativeModel(ScriptedModel):
    """Streams like Gemini: every chunk repeats the running usage totals."""

    def __init__(self, *a, prompt_tokens=9000, interrupt_after=None, **k):
        super().__init__(*a, **k)
        self.prompt_tokens, self.interrupt_after = prompt_tokens, interrupt_after

    def stream(self, messages):
        self.calls += 1
        text = self.answers.pop(0) if self.answers else "**Finding**\nNo answer."
        pieces = [text[i:i + 10] for i in range(0, len(text), 10)]
        for n, piece in enumerate(pieces, 1):
            if self.interrupt_after and n > self.interrupt_after:
                raise ConnectionError("stream interrupted")
            yield AIMessageChunk(content=piece, usage_metadata=_u(self.prompt_tokens, 5 * n))


def _plan(qtype, steps):
    return {"LLMPlan": {"question_type": qtype, "steps": [
        {"tool": s["tool"], "purpose": s["purpose"], "args_json": json.dumps(s.get("args", {}))} for s in steps]}}


@pytest.fixture()
def small_ok(monkeypatch):
    monkeypatch.setattr(get_settings(), "flo_min_denominator", 1)


def _run(runner, ds, q):
    evs = list(runner.start(session_id="ses_usage", question=q, dataset_id=ds, mode="connected", page="ask", filters=None))
    return evs


def test_action_proposal_reaches_approval_with_cumulative_streaming(runner, imported_id, small_ok):
    """Before the fix, a ~20-chunk Gemini-style stream summed to ~180k tokens and tripped the 24k budget."""
    plan = _plan("action_proposal", [
        {"tool": "get_resolution_breakdown", "purpose": "count outcomes"},
        {"tool": "propose_action", "purpose": "draft the action requested by the user",
         "args": {"title": "Review refund handling", "issue": "Unresolved refunds", "intervention": "Audit refund steps"}}])
    answer = "**Finding**\nSee the resolution counts [M1]. These are reported patterns, not verified causes.\n\n" * 3
    model = CumulativeModel(plans=plan, answers=[answer])
    set_model_override(model)
    try:
        evs = _run(runner, imported_id, "Propose an action to reduce unresolved refund issues")
    finally:
        set_model_override(None)
    kinds = [e["type"] for e in evs]
    assert "approval_required" in kinds, [e for e in evs if e["type"] in ("error", "node") and e.get("status") == "failed"]
    ans = evs[-1]
    assert ans["usage"]["input_tokens"] == 9000 + 100  # compose prompt once + the plan call
    assert ans["response"]["usage"]["reporting"] == ["cumulative"]


def test_interrupted_stream_fails_visibly_without_inflating_usage(runner, imported_id, small_ok):
    plan = _plan("analytics", [{"tool": "get_topic_counts", "purpose": "count"}])
    model = CumulativeModel(plans=plan, answers=["**Finding**\nBilling is the largest topic [M1] and more text."], interrupt_after=2)
    set_model_override(model)
    try:
        evs = _run(runner, imported_id, "What are the most common issues?")
    finally:
        set_model_override(None)
    ans = evs[-1]
    assert ans["status"] == "failed"
    assert any(e["type"] == "node" and e.get("node") == "compose_response" and e.get("status") == "failed" for e in evs)
    assert ans["usage"]["input_tokens"] < 9000  # the broken stream's usage is not counted as complete


def test_provider_exception_during_stream_is_a_model_failure(runner, imported_id, small_ok):
    model = ScriptedModel(plans=_plan("analytics", [{"tool": "get_topic_counts", "purpose": "count"}]))
    model.stream = lambda messages: (_ for _ in ()).throw(RuntimeError("503 high demand"))
    set_model_override(model)
    try:
        evs = _run(runner, imported_id, "What are the most common issues?")
    finally:
        set_model_override(None)
    assert evs[-1]["status"] == "failed"
    assert "503" in json.dumps(evs[-1]["response"])


@pytest.mark.parametrize("used, raises", [(24000, False), (24001, True)])
def test_token_budget_boundary(used, raises):
    state = {"tokens_in": used - 1000, "tokens_out": 1000}
    if raises:
        with pytest.raises(nodes.BudgetExceeded):
            nodes._guard(state, {}, "compose_response")
    else:
        nodes._guard(state, {}, "compose_response")


def test_explicit_action_request_gets_action_steps_when_model_omits_them(runner, imported_id, small_ok):
    """Seen live: gemini-3.5-flash-lite planned only counts + search for 'Propose an action ...'."""
    model = CumulativeModel(plans=_plan("investigation", [{"tool": "get_topic_counts", "purpose": "count"}]),
                            answers=["**Finding**\nSee the brief [M1]. These are reported patterns, not verified causes."])
    set_model_override(model)
    try:
        evs = _run(runner, imported_id, "Propose an action to reduce unresolved billing and refund issues.")
    finally:
        set_model_override(None)
    assert "approval_required" in [e["type"] for e in evs]
    planned = [e["tool"] for e in evs if e["type"] == "tool" and e.get("status") == "ok"]
    assert "prepare_decision_brief" in planned and "propose_action" in planned


def test_tool_events_show_the_models_arguments(runner, imported_id, small_ok):
    plan = _plan("evidence", [{"tool": "search_conversations", "purpose": "find examples", "args": {"query": "refund not received", "k": 4}}])
    model = CumulativeModel(plans=plan, answers=["**Finding**\nExamples are listed [E1]."])
    set_model_override(model)
    try:
        evs = _run(runner, imported_id, "Show examples of refund problems")
    finally:
        set_model_override(None)
    running = next(e for e in evs if e["type"] == "tool" and e["status"] == "running")
    assert running["args"] == {"query": "refund not received", "k": 4}  # filters are shown separately
