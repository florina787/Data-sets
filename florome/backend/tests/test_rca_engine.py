"""Pure RCA engine tests: hypothesis tests, classification rules and conclusions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from florome.rca.challenger import challenge
from florome.rca.engine import EvidenceItem, Topology, analyse

T0 = datetime(2026, 11, 10, 12, 0, tzinfo=UTC)


def topo() -> Topology:
    res = {r: {"name": r, "kind": k, "platform": "x"} for r, k in
           [("up", "lambda"), ("mid", "databricks_job"), ("api", "app_service"), ("biz", "business_process")]}
    return Topology(res, [("up", "mid", "data_flow"), ("mid", "api", "data_flow"), ("api", "biz", "serves")])


def ev(i: str, r: str, kind: str, minute: int, summary: str, **payload) -> EvidenceItem:
    return EvidenceItem(i, r, kind, T0 + timedelta(minutes=minute), summary, payload, "test")


def err(i, r, m, msg):
    return ev(i, r, "log", m, msg, level="ERROR", message=msg)


INC = {"primary_resource_id": "api"}


def by_title(report, needle):
    return next(h for h in report["hypotheses"] if needle in h["title"])


def test_change_with_signature_and_no_upstream_anomaly_is_confirmed():
    evidence = [ev("d1", "up", "deployment", -30, "up v2 deployed", previous_version="v1", signature_terms=["ParserV2"]),
                err("e1", "up", -28, "ParserV2 rejected record"), err("e2", "mid", -20, "input from up incomplete"),
                err("e3", "api", -10, "mid output empty")]
    r = analyse(INC, topo(), evidence)
    h = by_title(r, "Deployment on up")
    assert h["status"] == "confirmed"
    assert {t["test"]: t["result"] for t in h["tests"]} == {"temporal_precedence": "pass", "proximity": "pass", "signature_match": "pass",
                                                             "no_earlier_upstream_anomaly": "pass", "dependency_path": "pass"}
    assert r["conclusion"]["status"] == "confirmed" and r["conclusion"]["root_resource_id"] == "up"
    assert [c["resource_id"] for c in r["conclusion"]["causal_chain"]] == ["up", "mid", "api"]
    assert "e1" in h["supporting_evidence"]


def test_change_without_error_text_is_only_probable():
    evidence = [ev("d1", "up", "deployment", -30, "up v2", signature_terms=["ParserV2"]),
                ev("m1", "up", "metric", -25, "errors", name="Errors", value=50, threshold=5, direction="above"),
                err("e3", "api", -10, "mid output empty")]
    h = by_title(analyse(INC, topo(), evidence), "Deployment on up")
    assert h["status"] == "probable"
    assert next(t for t in h["tests"] if t["test"] == "signature_match")["result"] == "unknown"


def test_change_after_onset_is_disproven():
    evidence = [err("e1", "api", -40, "boom"), ev("c1", "api", "config_change", -10, "setting changed", signature_terms=["setting"])]
    h = by_title(analyse(INC, topo(), evidence), "Config Change on api")
    assert h["status"] == "disproven"
    assert h["contradicting_evidence"] == ["e1"]


def test_local_change_unrelated_to_errors_with_earlier_upstream_failure_is_disproven():
    evidence = [err("e0", "up", -50, "upstream broken"), ev("c1", "api", "config_change", -45, "autoscale changed", signature_terms=["autoscale"]),
                err("e3", "api", -10, "up data missing")]
    h = by_title(analyse(INC, topo(), evidence), "Config Change on api")
    assert h["status"] == "disproven"
    assert "e0" in h["contradicting_evidence"]


def test_saturation_is_disproven_by_normal_capacity_and_never_confirmed():
    normal = [err("e3", "api", -10, "x"), ev("m", "api", "metric", -12, "cpu", name="cpu", value=30, threshold=80, capacity=True)]
    assert by_title(analyse(INC, topo(), normal), "saturation")["status"] == "disproven"
    hot = [err("e3", "api", -10, "x"), ev("m", "api", "metric", -12, "cpu", name="cpu", value=97, threshold=80, capacity=True)]
    r = analyse(INC, topo(), hot)
    assert by_title(r, "saturation")["status"] == "probable"


def test_competing_probable_explanations_make_the_conclusion_inconclusive():
    evidence = [ev("d1", "api", "deployment", -30, "api v9", signature_terms=["zzz"]),
                ev("m0", "api", "metric", -15, "5xx", name="5xx", value=9, threshold=2, direction="above"),
                ev("m", "api", "metric", -16, "cpu", name="cpu", value=97, threshold=80, capacity=True)]
    c = analyse(INC, topo(), evidence)["conclusion"]
    assert c["status"] == "inconclusive" and c["competing_hypotheses"]


def test_no_evidence_gives_inconclusive_with_next_diagnostics():
    c = analyse(INC, topo(), [])["conclusion"]
    assert c["status"] == "inconclusive" and c["root_hypothesis_id"] is None and c["next_diagnostics"]


def test_challenger_downgrades_confirmed_when_chain_is_unlinked_and_never_upgrades():
    evidence = [ev("d1", "up", "deployment", -30, "up v2", signature_terms=["ParserV2"]), err("e1", "up", -28, "ParserV2 failed"),
                ev("m3", "api", "metric", -10, "5xx", name="5xx", value=9, threshold=2)]  # no anomaly on mid: chain cannot link
    t = topo()
    r = analyse(INC, t, evidence)
    assert r["conclusion"]["status"] == "confirmed"
    ch = challenge(r, t, evidence)
    assert ch["final_status"] == "probable" and "causal_chain_gaps" in ch["downgraded_by"]
    weak = analyse(INC, t, [])
    assert challenge(weak, t, [])["final_status"] == "inconclusive"


def test_no_numeric_confidence_is_emitted():
    evidence = [ev("d1", "up", "deployment", -30, "v2", signature_terms=["P"]), err("e1", "up", -28, "P failed")]
    r = analyse(INC, topo(), evidence)
    for h in r["hypotheses"]:
        assert "confidence" not in h and isinstance(h["basis"], str) and h["basis"].startswith("Passed:")
