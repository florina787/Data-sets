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
