"""Evaluation metrics: hand-checked values, empty inputs, and the review accuracy report."""
import math

from app.evaluation.metrics import (
    classification_report,
    ndcg_at_k,
    ranking_report,
    reciprocal_rank,
)


def test_classification_report_hand_checked():
    pairs = [("a", "a"), ("a", "b"), ("b", "b"), ("b", "b"), ("unknown", "a")]
    r = classification_report(pairs)
    assert r["n"] == 5 and r["accuracy"] == 0.6
    assert r["per_class"]["a"] == {"precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 2}
    assert r["per_class"]["b"]["precision"] == round(2 / 3, 4) and r["per_class"]["b"]["recall"] == 1.0
    assert r["per_class"]["unknown"]["recall"] == 0.0 and r["per_class"]["unknown"]["support"] == 1
    assert r["confusion"]["a"] == {"a": 1, "b": 1}
    assert r["macro_f1"] == round((0.5 + 0.8 + 0.0) / 3, 4)
    assert r["weighted_f1"] == round((0.5 * 2 + 0.8 * 2 + 0) / 5, 4)


def test_empty_inputs_return_none_not_zero():
    assert classification_report([])["accuracy"] is None
    assert ranking_report([]) == {"queries": 0}
    assert ndcg_at_k([], 5) is None


def test_ranking_metrics_hand_checked():
    assert reciprocal_rank([False, True, False]) == 0.5
    assert reciprocal_rank([False, False]) == 0.0
    assert math.isclose(ndcg_at_k([True, False, True], 3, total_relevant=2), (1 + 1 / 2) / (1 + 1 / math.log2(3)))
    r = ranking_report([[True, False], [False, False]], k=2, total_relevant=[4, 1])
    assert r["precision@2"] == 0.25 and r["mrr"] == 0.5 and r["irrelevant_evidence_rate"] == 0.75
    assert r["recall@2"] == round((1 / 4 + 0) / 2, 4)


def test_review_accuracy_includes_classification_report(client, demo_ids):
    ds = demo_ids["multilingual"]
    item = client.get(f"/api/datasets/{ds}/review/next").json()["item"]
    labels = {"primary_topic": "unknown", "resolution_status": "unknown", "sentiment_start": "neutral",
              "sentiment_end": "unknown", "escalation_requested": "no"}
    assert client.post(f"/api/datasets/{ds}/review/{item['conversation_key']}", json={"reviewer": "m", "labels": labels}).status_code == 200
    acc = client.get(f"/api/datasets/{ds}/review/accuracy").json()
    rep = next(iter(acc["systems"].values()))["escalation_requested"]["classification"]
    assert rep["n"] == 1 and "no" in rep["per_class"] and rep["confusion"]
