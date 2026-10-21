from app.analytics.extractor import enforce_evidence
from app.llm.provider import _inline_schema
from app.models.schemas import ConversationBatchAnalysis
from app.security.redaction import redact


def test_inline_schema_has_no_refs_and_requires_every_field():
    s = _inline_schema(ConversationBatchAnalysis)
    text = str(s)
    assert "$ref" not in text and "$defs" not in text and "maxItems" not in text
    item = s["properties"]["items"]["items"]
    assert "evidence" in item["required"] and "conversation_key" in item["required"]


def test_labels_without_validated_evidence_are_downgraded():
    f = enforce_evidence({"primary_topic": "billing_refunds", "resolution_status": "resolved_confirmed",
                          "escalation_requested": "yes", "secondary_topics": ["cancellation"],
                          "evidence": [{"supports": "resolution_status", "quote": "works now"}]})
    assert f["resolution_status"] == "resolved_confirmed"  # supported
    assert f["primary_topic"] == "unknown" and f["secondary_topics"] == []
    assert f["escalation_requested"] == "unknown"
    assert f["unsupported_labels_downgraded"] == {"primary_topic": "billing_refunds", "escalation_requested": "yes"}


def test_greeting_names_are_redacted_but_not_brands_or_common_words():
    assert redact("@123 Hi Debbie, what flight are you on?")[0] == "@[CUSTOMER] Hi [NAME], what flight are you on?"
    assert redact("Hi there, thanks")[0] == "Hi there, thanks"
    assert redact("Hey Apple your app is broken")[0] == "Hey Apple your app is broken"


def test_agent_signoffs_are_redacted_in_support_messages_only():
    cases = {
        "look into this for you. -RK": "look into this for you. [AGENT]",
        "any other questions /LM": "any other questions [AGENT]",
        "the right of the item.^EM": "the right of the item. [AGENT]",
        "from your confirmation email :) ~ Jess": "from your confirmation email :) [AGENT]",
        "See you!- Anwar": "See you! [AGENT]",
        "Sorry for any problems this causes. Lewis": "Sorry for any problems this causes. [AGENT]",
    }
    for raw, want in cases.items():
        assert redact(raw, agent=True)[0] == want
    assert redact("We will look into it. Thanks", agent=True)[0] == "We will look into it. Thanks"
    assert redact("my flight to JFK. Lewis", agent=False)[0] == "my flight to JFK. Lewis"


def test_channel_handoff_is_observed_from_messages():
    from app.analytics.rules import Msg, channel_handoff
    ask = [Msg("1", "customer", "my refund is late", "en"), Msg("2", "support", "Sorry! Please DM us your order number.", "en")]
    assert channel_handoff(ask)[0] == "requested"
    assert channel_handoff(ask + [Msg("3", "customer", "sent", "en")])[0] == "confirmed"
    assert channel_handoff([ask[0], Msg("2", "support", "We have processed the refund.", "en")])[0] == "none"
    assert channel_handoff([ask[0]])[0] == "unknown"


def test_batch_cache_does_not_copy_a_label_twice(imported_id, demo_ids, monkeypatch):
    """A conversation that already holds a (copied or imported) label is served from its own row."""
    from sqlalchemy import func, select
    from app.analytics import extractor
    from app.db import session_scope
    from app.graph.prompts import EXTRACT_BATCH_VERSION
    from app.models.orm import Analysis, Conversation

    monkeypatch.setattr(extractor, "provider_status", lambda: {"model_id": "fake-model"})
    with session_scope() as db:
        a = db.scalars(select(Conversation).where(Conversation.dataset_id == imported_id)).first()
        other = db.scalars(select(Conversation).where(Conversation.dataset_id == demo_ids["demo"])).first()
        row = dict(method="llm", model_id="fake-model", prompt_version=EXTRACT_BATCH_VERSION, content_hash=a.content_hash,
                   source_text="original", fields={"primary_topic": "unknown"}, status="ok")
        db.add(Analysis(conversation_id=other.id, **row))  # older row elsewhere: the cross-dataset cache source
        db.flush()
        db.add(Analysis(conversation_id=a.id, **row))      # this conversation already has its copy
        aid = a.id
    r = extractor.analyze_batch([aid], model=object())
    assert r == {"ok": 0, "failed": 0, "cached": 1}
    with session_scope() as db:
        assert db.scalar(select(func.count(Analysis.id)).where(Analysis.conversation_id == aid, Analysis.model_id == "fake-model")) == 1
