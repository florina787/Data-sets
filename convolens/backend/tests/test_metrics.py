from sqlalchemy import func, select

from app.analytics import metrics
from app.analytics.rules import Msg, analyze, validate_evidence
from app.db import session_scope
from app.models.orm import Analysis, Conversation, Message
from app.models.schemas import Filters
from app.tools.catalog import resolve_evidence


def test_breakdown_denominators_include_unknown(demo_ids):
    ds = demo_ids["demo"]
    with session_scope() as db:
        total = db.scalar(select(func.count()).where(Conversation.dataset_id == ds))
        for field in metrics.GROUPABLE:
            r = metrics.breakdown(db, ds, None, field)
            assert r["denominator"] == total
            assert sum(i["count"] for i in r["items"]) == total
            assert any(i["key"] == "unknown" for i in r["items"])  # unknown always shown, even when zero
            assert r["unknown"] == next(i["count"] for i in r["items"] if i["key"] == "unknown")


def test_chart_filter_table_consistency(demo_ids, client):
    """The same filter yields identical counts across breakdown, cross-tab, time series and the explorer table."""
    ds = demo_ids["demo"]
    import json
    f = {"topics": ["billing_refunds"]}
    q = json.dumps(f)
    b = client.get(f"/api/datasets/{ds}/breakdown/resolution_status", params={"filters": q}).json()
    xt = client.get(f"/api/datasets/{ds}/crosstab", params={"rows": "primary_topic", "cols": "resolution_status", "filters": q}).json()
    ts = client.get(f"/api/datasets/{ds}/timeseries", params={"filters": q}).json()
    table = client.get(f"/api/datasets/{ds}/conversations", params={"filters": q, "page_size": 5}).json()
    assert b["denominator"] == xt["denominator"] == ts["denominator"] == table["total"]
    row = xt["rows"][0]
    assert {c["key"]: c["count"] for c in row["cells"]} == {i["key"]: i["count"] for i in b["items"]} | {
        k: 0 for k in {c["key"] for c in row["cells"]} - {i["key"] for i in b["items"]}}
    # Clicking a bar (resolution = unresolved) in the chart opens matching conversations in the explorer.
    unres = next(i["count"] for i in b["items"] if i["key"] == "unresolved_explicit")
    f2 = json.dumps({**f, "resolution": ["unresolved_explicit"]})
    assert client.get(f"/api/datasets/{ds}/conversations", params={"filters": f2}).json()["total"] == unres


def test_filters_reject_unknown_fields_and_values():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Filters(topics=["DROP TABLE"])
    with pytest.raises(ValidationError):
        Filters(sql="select 1")  # extra fields forbidden
    with pytest.raises(ValidationError):
        Filters(brands=["x'; --"])


def test_unknown_outcome_when_no_signal():
    r = analyze([Msg("1", "customer", "@Brand hello there, quick question about my plan", "en"),
                 Msg("2", "support", "@[CUSTOMER] Hi! What would you like to know?", "en")])
    assert r["resolution_status"] == "unknown"
    assert r["sentiment_end"] == "unknown"  # only one customer turn: end sentiment unobserved


def test_non_covered_language_is_unknown_not_guessed():
    r = analyze([Msg("1", "customer", "注文した商品がまだ届きません", "ja"), Msg("2", "support", "@[CUSTOMER] DMでご連絡ください", "ja")])
    assert r["primary_topic"] == "unknown" and r["escalation_requested"] == "unknown" and r["sentiment_start"] == "unknown"


def test_evidence_spans_validate_against_stored_text():
    texts = {"1": "my refund still hasn't arrived"}
    valid, invalid = validate_evidence([{"message_id": "1", "quote": "refund still", "supports": "x"},
                                        {"message_id": "1", "quote": "refund arrived", "supports": "x"},
                                        {"message_id": "9", "quote": "refund", "supports": "x"}], texts)
    assert len(valid) == 1 and valid[0]["start"] == 3 and valid[0]["end"] == 15
    assert len(invalid) == 2


def test_all_stored_rules_evidence_resolves(demo_ids):
    ds = demo_ids["demo"]
    with session_scope() as db:
        rows = db.execute(select(Conversation.key, Analysis.fields).join(Analysis, Analysis.id == Conversation.analysis_id)
                          .where(Conversation.dataset_id == ds)).all()
        ids = [metrics.evidence_id(k, e["message_id"], e["start"], e["end"]) for k, f in rows for e in f["evidence"]]
        assert ids
        for i in range(0, len(ids), 20):
            r = resolve_evidence(db, ds, ids[i:i + 20])
            assert r["invalid"] == 0
        bad = resolve_evidence(db, ds, [ids[0].split("#")[0] + "#0-99999", "cv_0000000000000000/1"])
        assert bad["invalid"] == 2


def test_evidence_ids_are_scoped_to_dataset(demo_ids):
    with session_scope() as db:
        conv = db.scalar(select(Conversation).where(Conversation.dataset_id == demo_ids["demo"]))
        m = db.scalar(select(Message).where(Message.conversation_id == conv.id))
        eid = metrics.evidence_id(conv.key, m.source_id)
        assert resolve_evidence(db, demo_ids["demo"], [eid])["valid"] == 1
        assert resolve_evidence(db, demo_ids["multilingual"], [eid])["valid"] == 0
