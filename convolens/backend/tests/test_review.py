"""Blind review queue: deterministic order, validation, reveal-after-submit and accuracy scoring."""
from app.analytics.review import wilson


def test_review_flow_and_accuracy(client, demo_ids):
    ds = demo_ids["demo"]
    r = client.get(f"/api/datasets/{ds}/review/next").json()
    item = r["item"]
    assert item and item["messages"] and r["reviewed"] == 0
    assert "primary_topic" not in item  # blind: no system labels before submitting
    assert client.get(f"/api/datasets/{ds}/review/next").json()["item"]["conversation_key"] == item["conversation_key"]

    labels = {"primary_topic": "unknown", "resolution_status": "unknown", "sentiment_start": "neutral",
              "sentiment_end": "unknown", "escalation_requested": "no"}
    bad = client.post(f"/api/datasets/{ds}/review/{item['conversation_key']}", json={"reviewer": "t", "labels": {**labels, "sentiment_end": "furious"}})
    assert bad.status_code == 422
    ok = client.post(f"/api/datasets/{ds}/review/{item['conversation_key']}", json={"reviewer": "t", "labels": labels}).json()
    assert ok["saved"] and ok["reviewed"] == 1 and ok["comparison"]
    dup = client.post(f"/api/datasets/{ds}/review/{item['conversation_key']}", json={"reviewer": "t", "labels": labels})
    assert dup.status_code == 409
    assert client.get(f"/api/datasets/{ds}/review/next").json()["item"]["conversation_key"] != item["conversation_key"]

    acc = client.get(f"/api/datasets/{ds}/review/accuracy").json()
    assert acc["reviewed"] == 1
    fields = next(iter(acc["systems"].values()))
    assert fields["escalation_requested"]["n"] == 1 and fields["escalation_requested"]["ci95"]


def test_wilson_interval():
    assert wilson(0, 0) is None
    lo, hi = wilson(80, 100)
    assert 0.70 < lo < 0.80 < hi < 0.88
