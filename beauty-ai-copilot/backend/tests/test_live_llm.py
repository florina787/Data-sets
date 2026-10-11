"""Optional live LLM test. Skipped unless LIVE_LLM_TESTS=1 and ANTHROPIC_API_KEY are set.
Budget: one short call (≤ 800 output tokens). Records provider, model, prompt and usage."""
import os

import pytest

pytestmark = pytest.mark.live_llm


@pytest.mark.skipif(os.getenv("LIVE_LLM_TESTS") != "1" or not os.getenv("ANTHROPIC_API_KEY"), reason="live LLM tests not enabled")
def test_live_summary_is_schema_valid(env):
    env["monkeypatch"].setenv("LLM_MODE", "live")
    env["monkeypatch"].setenv("ANTHROPIC_API_KEY", os.environ["ANTHROPIC_API_KEY"])
    from app.agents import llm
    from app.config import reset_settings
    reset_settings(); llm.reset_provider()
    p = llm.get_provider()
    res = p.summarize("summary_evaluation", {"summary": "Computed outcome: FAIL. Worst cell TS-3|cool_fluorescent -4.31 pp.",
                                             "data": {"outcome": "FAIL"}}, budget_remaining=10000)
    print({"provider": res.provider, "model": res.model, "prompt": res.prompt_id, "in": res.input_tokens, "out": res.output_tokens,
           "cost": res.cost_usd, "error": res.error})
    assert res.error is None and res.output is not None
    from app.agents.agents import summary_contradicts
    assert not summary_contradicts("evaluation", "FAIL", res.output.summary)
