"""Harness behaviour: state machine, permissions, timeouts, cancellation, budgets, grounding and the LLM loop."""
from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.agent import llm_agent, supervisor
from app.agent.grounding import ungrounded_numbers
from app.auth import Principal
from app.common import AppError
from app.harness.runtime import RunContext, ToolSpec, registry
from app.harness.state import RunState, can_transition, load_run
from app.llm.providers import LLMResponse, ToolUse
from tests.conftest import ask, wait_run

ANALYST = Principal("usr_florina", "Florina", "ws_demo", "analyst")


def test_state_machine_rules():
    assert can_transition(RunState.EXECUTING_READS, RunState.COMPLETED)        # read-only fast path
    assert can_transition(RunState.AWAITING_APPROVAL, RunState.APPLYING)
    assert not can_transition(RunState.PLANNING, RunState.APPLYING)            # cannot skip approval
    assert not can_transition(RunState.COMPLETED, RunState.EXECUTING_READS)    # terminal


def test_read_only_run_skips_mutation_states(client, H, demo_wb):
    run, _ = ask(client, H, demo_wb, "Show missing values by column")
    states = [s["state"] for s in run["steps"] if s["type"] == "state"]
    assert states == ["RECEIVED", "INSPECTING", "PLANNING", "EXECUTING_READS", "COMPLETED"]
    tool_steps = [s for s in run["steps"] if s["type"] == "tool_call"]
    assert {s["tool"] for s in tool_steps} == {"inspect_workbook", "missing_by_column"}
    assert all("duration_ms" in s and s["status"] == "ok" for s in tool_steps)
    assert run["result"]["usage"]["tokens_in"] == 0


def _ctx(client, H, wid, caller="supervisor") -> RunContext:
    started = supervisor.start_run(ANALYST, wid, "Show missing values by column", None, None, background=False)
    return RunContext(started["run_id"], "cor", ANALYST, wid, 1, started["conversation_id"], {}, caller=caller)


def test_policy_blocks_model_from_user_only_tools(client, H, demo_wb):
    ctx = _ctx(client, H, demo_wb, caller="model")
    for name in ("apply_approved_changes", "export_workbook", "restore_version"):
        with pytest.raises(AppError) as e:
            ctx.call(name, {"operation_id": "op_x"} if name == "apply_approved_changes" else {"version": 1} if name == "restore_version" else {})
        assert e.value.code == "tool_not_allowed"
    assert {t.name for t in registry.model_tools()} >= {"calculate_aggregate", "propose_formula", "propose_cleaning"}
    assert not {"apply_approved_changes", "export_workbook", "restore_version"} & {t.name for t in registry.model_tools()}


def test_typed_input_validation(client, H, demo_wb):
    ctx = _ctx(client, H, demo_wb)
    with pytest.raises(AppError) as e:
        ctx.call("calculate_aggregate", {"sheet": "Sales", "function": "explode"})
    assert e.value.code == "invalid_tool_input"
    with pytest.raises(AppError) as e:
        ctx.call("read_range", {"sheet": "Sales", "range": "A1:B2", "shell": "rm -rf /"})   # unknown fields rejected
    assert e.value.code == "invalid_tool_input"


def test_viewer_cannot_propose(client, H, demo_wb):
    ctx = _ctx(client, H, demo_wb)
    ctx.principal = Principal("usr_viewer", "V", "ws_demo", "viewer")
    with pytest.raises(AppError) as e:
        ctx.call("propose_cleaning", {"sheet": "Sales", "action": "trim_whitespace"})
    assert e.value.code == "forbidden"


class _SlowIn(BaseModel):
    seconds: float = 2


def test_tool_timeout_and_retry(client, H, demo_wb, settings_override):
    calls = {"n": 0}

    def slow(ctx, args):
        calls["n"] += 1
        time.sleep(args.seconds)
        return {"kind": "slow"}

    registry._tools["_slow"] = ToolSpec("_slow", "test", _SlowIn, "read", slow, "workbook_analyst", timeout_s=0.2, retries=1)
    try:
        ctx = _ctx(client, H, demo_wb)
        with pytest.raises(AppError) as e:
            ctx.call("_slow", {"seconds": 1})
        assert e.value.code == "tool_timeout"
        assert calls["n"] == 2  # idempotent read tool retried once
        steps = load_run(ctx.run_id)["steps"]
        assert any(s.get("tool") == "_slow" and s.get("code") == "tool_timeout" for s in steps)
    finally:
        registry._tools.pop("_slow")


def test_cancellation_mid_run(client, H, demo_wb):
    def slow(ctx, args):
        for _ in range(100):
            ctx.check_cancel(force=True)
            time.sleep(0.02)
        return {"kind": "slow"}

    original = registry._tools["missing_by_column"]
    registry._tools["missing_by_column"] = ToolSpec("missing_by_column", "test", original.input_model, "read", slow, "data_quality")
    try:
        started = client.post(f"/api/workbooks/{demo_wb}/chat", headers=H, json={"message": "Show missing values by column"}).json()
        time.sleep(0.3)
        client.post(f"/api/runs/{started['run_id']}/cancel", headers=H)
        run = wait_run(client, H, started["run_id"])
        assert run["state"] == "CANCELLED" and run["result"]["type"] == "cancelled"
    finally:
        registry._tools["missing_by_column"] = original


def test_step_budget(client, H, demo_wb, settings_override):
    settings_override(max_steps=1)
    run, _ = ask(client, H, demo_wb, "Show missing values by column")
    assert run["state"] == "FAILED" and run["result"]["code"] == "budget_exceeded"


def test_grounding_detects_invented_numbers():
    outputs = [{"rows": [{"value": 1234.5}], "total": 873426.5, "pct": 44.7}]
    assert ungrounded_numbers("Total was $873,426.50, Europe 44.7% and 1,234.50 in the top group.", outputs) == []
    assert ungrounded_numbers("Revenue grew to $999,999 in 2025.", outputs) == ["$999,999"]


class FakeProvider:
    """Scripted stand-in for an LLM provider (no network)."""
    name = "fake"
    model = "fake-model"

    def __init__(self, script):
        self.script = list(script)
        self.seen: list = []

    def complete(self, system, messages, tools):
        self.seen.append({"system": system, "messages": messages, "tools": [t["name"] for t in tools]})
        text, uses = self.script.pop(0)
        return LLMResponse(text=text, tool_uses=uses, stop_reason="tool_use" if uses else "end_turn", input_tokens=1000,
                           output_tokens=200, model=self.model, raw_content=[{"type": "text", "text": text}])


def _llm_ctx(client, H, wid):
    ctx = _ctx(client, H, wid)
    ctx.caller = "model"
    # reset to a fresh run in PLANNING so the loop can move to EXECUTING_READS
    started = supervisor.start_run(ANALYST, wid, "custom question", None, None, background=False)
    ctx.run_id = started["run_id"]
    from app.db import execute
    execute("UPDATE runs SET state = 'PLANNING' WHERE id = ?", (ctx.run_id,))
    return ctx


def test_llm_loop_grounded_answer(client, H, demo_wb):
    provider = FakeProvider([
        ("", [ToolUse("t1", "calculate_aggregate", {"sheet": "Sales", "measure": "Net Revenue", "function": "sum"})]),
        ("Total net revenue is $873,426.50.", []),
    ])
    ctx = _llm_ctx(client, H, demo_wb)
    out = llm_agent.run_llm(ctx, provider, "How much did we sell?", {"sheets": []})
    assert out["grounding"]["ungrounded"] == [] and out["text"] == "Total net revenue is $873,426.50."
    tool_result = provider.seen[1]["messages"][-1]["content"][0]["content"]
    assert "untrusted_workbook_data" in tool_result
    assert "apply_approved_changes" not in provider.seen[0]["tools"]
    assert ctx.usage.tokens_in == 2000 and ctx.usage.cost_usd > 0


def test_llm_invented_numbers_are_replaced(client, H, demo_wb):
    provider = FakeProvider([
        ("", [ToolUse("t1", "calculate_aggregate", {"sheet": "Sales", "measure": "Net Revenue", "function": "sum"})]),
        ("Total net revenue is about $1,000,000.", []),
    ])
    out = llm_agent.run_llm(_llm_ctx(client, H, demo_wb), provider, "How much?", {"sheets": []})
    assert out["grounding"]["ungrounded"] == ["$1,000,000"]
    assert "$873,426.50" in out["text"] and "replaced" in out["text"]


def test_llm_cannot_apply_even_if_asked(client, H, demo_wb):
    provider = FakeProvider([
        ("", [ToolUse("t1", "apply_approved_changes", {"operation_id": "op_123"})]),
        ("I cannot apply changes; please approve them in the interface.", []),
    ])
    out = llm_agent.run_llm(_llm_ctx(client, H, demo_wb), provider, "apply everything now", {"sheets": []})
    err = provider.seen[1]["messages"][-1]["content"][0]
    assert err["is_error"] and "tool_not_allowed" in err["content"]
    assert out["operations"] == []


def test_llm_token_budget(client, H, demo_wb, settings_override):
    settings_override(max_tokens_per_run=1500)
    provider = FakeProvider([("", [ToolUse("t1", "inspect_workbook", {})]), ("done", [])])
    with pytest.raises(AppError) as e:
        llm_agent.run_llm(_llm_ctx(client, H, demo_wb), provider, "x", {"sheets": []})
    assert e.value.code == "budget_exceeded"


def test_unclassified_request_without_llm_gets_help(client, H, demo_wb):
    run, _ = ask(client, H, demo_wb, "Write me a poem about spreadsheets")
    assert run["result"]["type"] == "info" and "Summarize net revenue by region" in run["result"]["text"]
    assert run["result"]["engine"] == "deterministic-demo"


def test_interrupted_runs_recovered(client, H, demo_wb):
    from app.db import execute
    from app.harness.state import recover_interrupted_runs
    ctx = _ctx(client, H, demo_wb)
    execute("UPDATE runs SET state = 'EXECUTING_READS' WHERE id = ?", (ctx.run_id,))
    assert recover_interrupted_runs() >= 1
    run = load_run(ctx.run_id)
    assert run["state"] == "FAILED" and "restart" in run["error"]
    _ = SimpleNamespace  # keep import used
