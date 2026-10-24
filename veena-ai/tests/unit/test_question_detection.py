import pytest

from backend.agents.question_detection import QuestionDetector, classify_rules
from tests.conftest import ScriptedLLM


@pytest.mark.parametrize(
    "text,intent",
    [
        ("How does a hash map handle collisions?", "coding"),
        ("Can you explain the CAP theorem?", "architecture"),
        ("Design a scalable notification system", "architecture"),
        ("Tell me about a time you disagreed with your manager", "behavioral"),
        ("What do you mean by eventual consistency?", "clarification"),
        ("What about the write path?", "follow_up"),
        ("Why is this Python function throwing a KeyError?", "coding"),
        ("Summarize the meeting so far", "command"),
        ("What is the capital of Australia?", "question"),
    ],
)
def test_rules_intents(text, intent):
    is_q, got, conf = classify_rules(text)
    assert is_q, text
    assert got == intent
    assert conf >= 0.3


@pytest.mark.parametrize("text", ["Thanks, that makes sense.", "Okay.", "I think we should ship on Friday", "yeah"])
def test_rules_statements(text):
    is_q, _, _ = classify_rules(text)
    assert not is_q


def test_pronoun_follow_up_with_history():
    _, intent, _ = classify_rules("Why does it do that?", has_history=True)
    assert intent == "follow_up"


async def test_duplicates_suppressed():
    d = QuestionDetector()
    a = await d.detect("How does a hash map handle collisions?", escalate=False)
    b = await d.detect("how does a hash map handle collisions", escalate=False)
    assert a.is_question and not a.duplicate
    assert b.duplicate


async def test_ambiguous_escalates_to_llm():
    llm = ScriptedLLM(json_reply={"is_question": True, "intent": "coding", "confidence": 0.9})
    d = QuestionDetector(llm=llm, model="qwen2.5:1.5b")
    # "so the cache layer" alone is ambiguous: no question mark, no wh-word.
    r = await d.detect("Could the cache layer", escalate=True)
    assert r.method == "llm" and r.intent == "coding" and r.confidence == 0.9
    assert llm.calls[0]["fmt"] == "json"


async def test_structured_result_fields():
    r = await QuestionDetector().detect("Explain this code please", context_ref="m1", escalate=False)
    d = r.to_dict()
    assert set(d) >= {"text", "intent", "confidence", "timestamp", "context_ref", "answer_mode"}
    assert d["context_ref"] == "m1" and d["answer_mode"] in ("code", "detailed")
