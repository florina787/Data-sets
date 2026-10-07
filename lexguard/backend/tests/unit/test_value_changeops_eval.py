"""ValueIQ, ChangeOps and Evaluation Lab."""

import pytest

from app.changeops import service as changeops
from app.evaluation import lab
from app.valueiq import service as valueiq


def test_value_estimate_deterministic():
    a = valueiq.estimate_run("WF-DD-COC", 487, review_items=63, deviations=11)
    assert a == valueiq.estimate_run("WF-DD-COC", 487, review_items=63, deviations=11)
    assert a["traditional_hours"] == 121.75 and a["lawyer_review_hours"] == 9.05
    assert a["net_hours_saved"] == round(121.75 - a["ai_processing_hours"] - 9.05, 2)
    assert "Synthetic" in a["label"]


def test_value_metrics_synthetic_stable(store):
    m1 = valueiq.metrics(store, include_live=False)
    m2 = valueiq.metrics(store, include_live=False)
    assert m1 == m2
    t = m1["totals"]
    assert round(t["traditional_hours"] - t["ai_processing_hours"] - t["lawyer_review_hours"] - t["rework_hours"], 1) == \
        t["net_hours_saved"] or abs(t["net_hours_saved"] - (t["traditional_hours"] - t["ai_processing_hours"]
                                                            - t["lawyer_review_hours"] - t["rework_hours"])) < 0.2


def test_changeops_finds_affected_workflows(store):
    r = changeops.analyze(store, "All AI-generated legal research for external use requires citation verification.")
    affected = {w["workflow_id"] for w in r["affected_workflows"]}
    compliant = {w["workflow_id"] for w in r["compliant_workflows"]}
    assert {"WF-RESEARCH-EXT", "WF-CLIENT-ALERT"} <= affected
    assert "WF-LIT-RESEARCH-BRIEF" in compliant  # already has citation verification
    assert "WF-RESEARCH-INT" not in affected      # internal only
    assert r["evaluation"]["passed"] and r["generated_tests"] and r["status"] == "PENDING_APPROVAL"
    assert "Litigation" in r["affected_practices"] and r["affected_providers"]


def test_changeops_unstructured_policy_is_not_guessed(store):
    assert changeops.analyze(store, "Be careful with AI please.")["status"] == "NEEDS_STRUCTURING"


def test_regression_evaluation_baseline_vs_candidate(store):
    r = lab.compare(store, "DUE_DILIGENCE_AGENT")
    by = {m["metric"]: m for m in r["metrics"]}
    assert r["gates_passed"] and by["cross_matter_isolation"]["candidate"] == 1.0
    assert by["citation_correctness"]["candidate"] > by["citation_correctness"]["baseline"]
    rag = lab.compare(store, "RAG_PIPELINE")
    by = {m["metric"]: m for m in rag["metrics"]}
    assert by["cross_matter_isolation"]["candidate"] == 1.0
    assert not rag["gates_passed"] and "retrieval_quality" in rag["failed_gates"]
    with pytest.raises(ValueError):
        lab.promote("RAG_PIPELINE", rag["run_id"], "U-007")
    promoted = lab.promote("DUE_DILIGENCE_AGENT", r["run_id"], "U-007")
    assert promoted["promoted_version"] == "1.4"
