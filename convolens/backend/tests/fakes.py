"""Scripted chat models for connected-mode tests (no network)."""
from langchain_core.messages import AIMessage, AIMessageChunk


class _Structured:
    def __init__(self, parent, schema):
        self.parent, self.schema = parent, schema

    def invoke(self, messages):
        if self.parent.fail:
            raise RuntimeError("simulated provider outage")
        value = self.parent.plans.get(self.schema.__name__)
        parsed = self.schema(**value) if isinstance(value, dict) else value
        return {"parsed": parsed, "raw": AIMessage(content="", usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}),
                "parsing_error": None}


class ScriptedModel:
    model_id = "scripted-test-model"

    def __init__(self, plans=None, answers=None, fail=False):
        self.plans = plans or {}
        self.answers = list(answers or [])
        self.fail = fail
        self.calls = 0

    def with_structured_output(self, schema, include_raw=False):
        return _Structured(self, schema)

    def stream(self, messages):
        if self.fail:
            raise RuntimeError("simulated provider outage")
        self.calls += 1
        text = self.answers.pop(0) if self.answers else "**Finding**\nNo answer."
        for i in range(0, len(text), 20):
            chunk = AIMessageChunk(content=text[i:i + 20])
            if i == 0:
                chunk = AIMessageChunk(content=text[i:i + 20], usage_metadata={"input_tokens": 200, "output_tokens": 50, "total_tokens": 250})
            yield chunk

    def invoke(self, messages):
        if self.fail:
            raise RuntimeError("simulated provider outage")
        return AIMessage(content=self.answers.pop(0) if self.answers else "")
