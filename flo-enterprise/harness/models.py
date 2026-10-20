"""Model provider adapters behind one interface.

* MockModel (default): deterministic, in-process. Renders narratives from registered templates using ONLY the facts
  supplied by tools, and plans tool calls from the agent's default plan. Token counts are estimates (chars / 4).
* BedrockModel: AWS Bedrock Converse API adapter (requires boto3 + credentials; never enabled implicitly). Prompts are
  tokenized by the privacy service before leaving the process; numeric grounding validation rejects any narrative with
  numbers not present in the facts, falling back to the deterministic renderer.
* ScriptedModel: test double that returns arbitrary (including malicious) tool-call proposals to prove that the tool
  gateway, not the model, enforces authorization.
Pricing constants are illustrative assumptions for cost estimation, not quotes.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass

from backend.config import get_settings


@dataclass
class Generation:
    text: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    model: str


def _est(s: str) -> int:
    return max(1, len(s) // 4)


TEMPLATES: dict[str, Callable[[dict], str]] = {}


def template(name: str):
    def deco(fn: Callable[[dict], str]):
        TEMPLATES[name] = fn
        return fn
    return deco


class ModelAdapter(ABC):
    name: str
    provider_key: str
    price_in: float = 0.0
    price_out: float = 0.0

    @abstractmethod
    def narrate(self, template_id: str, facts: dict, instructions: str = "") -> Generation: ...

    def plan(self, question: str, allowed_tools: list[str], default_plan: list[dict]) -> list[dict]:
        return default_plan


class MockModel(ModelAdapter):
    name = "mock-deterministic-1"
    provider_key = "mock-deterministic"

    def narrate(self, template_id: str, facts: dict, instructions: str = "") -> Generation:
        text = TEMPLATES[template_id](facts)
        prompt = instructions + json.dumps(facts, default=str)
        return Generation(text, _est(prompt), _est(text), 0.0, self.name)


class ScriptedModel(MockModel):
    name = "scripted-test-model"

    def __init__(self, proposals: list[dict]):
        self.proposals = proposals

    def plan(self, question: str, allowed_tools: list[str], default_plan: list[dict]) -> list[dict]:
        return list(self.proposals) + list(default_plan)


class BedrockModel(ModelAdapter):  # pragma: no cover - requires cloud credentials
    provider_key = "bedrock-ca-central-1"
    price_in, price_out = 3e-6, 15e-6

    def __init__(self, model_id: str = "anthropic.claude-sonnet"):
        import boto3
        self.name = f"bedrock:{model_id}"
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=get_settings().bedrock_region)

    def narrate(self, template_id: str, facts: dict, instructions: str = "") -> Generation:
        fallback = TEMPLATES[template_id](facts)
        prompt = (f"{instructions}\nWrite a concise executive narrative using ONLY these facts. Do not compute new numbers. "
                  f"Reference draft:\n{fallback}\nFacts (JSON):\n{json.dumps(facts, default=str)}")
        r = self.client.converse(modelId=self.model_id, messages=[{"role": "user", "content": [{"text": prompt}]}],
                                 inferenceConfig={"maxTokens": 800, "temperature": 0})
        text = r["output"]["message"]["content"][0]["text"]
        u = r.get("usage", {})
        tin, tout = u.get("inputTokens", _est(prompt)), u.get("outputTokens", _est(text))
        return Generation(text, tin, tout, tin * self.price_in + tout * self.price_out, self.name)


def default_model() -> ModelAdapter:
    if get_settings().model_provider == "bedrock":
        try:
            return BedrockModel()
        except Exception:  # noqa: BLE001 - missing credentials/SDK: fall back to the labelled mock
            return MockModel()
    return MockModel()
