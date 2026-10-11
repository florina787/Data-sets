"""Pure unit tests: lifecycle table, gate arithmetic, metrics, thresholds, redaction, parsing."""
import numpy as np
import pytest

from app.agents.agents import summary_contradicts
from app.agents.llm import parse_summary
from app.errors import PolicyViolation
from app.evaluation import metrics as M
from app.lifecycle.state_machine import S, TRANSITIONS, assert_transition, can_transition
from app.policies import engine as E
from app.security.redaction import redact

POLICY = {"policy_version": "t", "thresholds": {"min_samples_per_cell": 100, "max_regression_pp": 2.0,
          "target_min_improvement_pp": 5.0, "max_coverage_drop_pp": 3.0},
          "gate_owners": {k: "x" for k in ["G-CONFIG", "G-ARTIFACT", "G-AMBIGUITY", "G-EVIDENCE", "G-SAMPLES", "G-TARGET",
                                           "G-NO-REGRESSION", "G-COVERAGE", "G-ABSTENTION-DENOMINATOR", "G-CONTROLS"]}}


def cell(n=120, delta=0.0, cov=0.0):
    b = {"n_eligible": n}
    return {"baseline": b, "candidate": b, "delta": {"top1_delta_pp": delta, "coverage_delta_pp": cov}, "delta_ci95_pp": (delta - 3, delta + 3)}


def gates(cells, **kw):
    args = dict(policy=POLICY, thresholds=E.effective_thresholds(POLICY, {}), cells=cells, required_cells=list(cells) or ["A"],
                target_cell="T", controls=[{"test_id": "c", "status": "PASS"}], unresolved_required=0, requirement_approved=True,
                evidence_check={"missing": [], "invalid": [], "valid": 4}, artifact_check={"m": {"registered": "a", "computed": "a"}},
                config_present=True, integrity={"ok": True, "observed": ""})
    args.update(kw)
    return {g.gate_id: g.status for g in E.evaluation_gates(**args)}, E.evaluation_gates(**args)


@pytest.mark.parametrize("src,dst", [(a.value, b.value) for (a, b) in TRANSITIONS])
def test_every_legal_transition_is_permitted(src, dst):
    assert can_transition(src, dst)
    assert assert_transition(src, dst)


ILLEGAL = [("DRAFT", "RELEASED"), ("NEEDS_CLARIFICATION", "EVALUATING"), ("EVALUATION_FAILED", "RELEASE_APPROVED"),
           ("EVALUATION_INCONCLUSIVE", "REVIEW_REQUIRED"), ("REVIEW_REQUIRED", "CANARY"), ("RELEASE_APPROVED", "RELEASED"),
           ("ROLLED_BACK", "CANARY"), ("CANCELLED", "DRAFT"), ("FAILED", "DEVELOPMENT"), ("IMPACT_REVIEW", "EVALUATING"),
           ("RELEASED", "CANCELLED"), ("ROLLBACK_RECOMMENDED", "RELEASED")]


@pytest.mark.parametrize("src,dst", ILLEGAL)
def test_illegal_transitions_rejected(src, dst):
    with pytest.raises(PolicyViolation):
        assert_transition(src, dst)


def test_all_pairs_covered():
    states = [s.value for s in S]
    legal = sum(can_transition(a, b) for a in states for b in states)
    assert legal == len(TRANSITIONS)
    for t in ("ROLLED_BACK", "CANCELLED", "FAILED"):
        assert not any(can_transition(t, b) for b in states)


def test_regression_boundary_exact_threshold_passes():
    st, _ = gates({"A": cell(delta=-2.0), "T": cell(delta=5.0)}, required_cells=["A", "T"])
    assert st["G-NO-REGRESSION"] == "PASS" and st["G-TARGET"] == "PASS"


def test_regression_just_beyond_threshold_fails_despite_target_gain():
    st, g = gates({"A": cell(delta=-2.01), "T": cell(delta=15.0)}, required_cells=["A", "T"])
    assert st["G-NO-REGRESSION"] == "FAIL" and st["G-TARGET"] == "PASS"
    assert E.overall(g) == "FAIL"


def test_target_below_minimum_fails():
    st, _ = gates({"T": cell(delta=4.99)}, required_cells=["T"])
    assert st["G-TARGET"] == "FAIL"


def test_insufficient_samples_is_inconclusive_never_pass():
    st, g = gates({"A": cell(n=99), "T": cell(n=150, delta=8)}, required_cells=["A", "T"])
    assert st["G-SAMPLES"] == "INCONCLUSIVE"
    assert E.overall(g) == "INCONCLUSIVE"


def test_missing_required_cell_is_inconclusive():
    st, g = gates({"T": cell(delta=8)}, required_cells=["A", "T"])
    assert st["G-SAMPLES"] == "INCONCLUSIVE" and E.overall(g) != "PASS"


def test_artifact_mismatch_fails():
    st, _ = gates({"T": cell(delta=8)}, required_cells=["T"], artifact_check={"m": {"registered": "a", "computed": "b"}})
    assert st["G-ARTIFACT"] == "FAIL"


def test_unresolved_ambiguity_and_missing_evidence_block():
    st, g = gates({"T": cell(delta=8)}, required_cells=["T"], unresolved_required=1,
                  evidence_check={"missing": ["POL-REL-005"], "invalid": [], "valid": 0})
    assert st["G-AMBIGUITY"] == "INCONCLUSIVE" and st["G-EVIDENCE"] == "INCONCLUSIVE" and E.overall(g) != "PASS"


def test_failed_control_test_fails():
    st, _ = gates({"T": cell(delta=8)}, required_cells=["T"], controls=[{"test_id": "CT-X", "status": "FAIL"}])
    assert st["G-CONTROLS"] == "FAIL"


def test_empty_gates_are_inconclusive():
    assert E.overall([]) == "INCONCLUSIVE"


def test_thresholds_take_stricter_value():
    t = E.effective_thresholds(POLICY, {"min_samples_per_cell": 150, "max_regression_pp": 5.0, "target_min_improvement_pp": 3})
    assert t["min_samples_per_cell"] == 150 and t["max_regression_pp"] == 2.0 and t["target_min_improvement_pp"] == 5.0


def test_abstention_stays_in_denominator():
    exp = ["SH-01"] * 10
    preds = [{"abstained": False, "top3": ["SH-01", "SH-02", "SH-03"]}] * 4 + [{"abstained": True, "top3": []}] * 6
    s = M.summarize(M.indicators(exp, preds))
    assert s["n_eligible"] == 10 and s["top1_accuracy_pct"] == 40.0
    assert s["coverage_pct"] == 40.0 and s["conditional_top1_accuracy_pct"] == 100.0


def test_abstaining_model_does_not_look_better():
    exp = ["SH-01"] * 100
    base = [{"abstained": False, "top3": ["SH-01", "SH-02", "SH-03"]}] * 70 + [{"abstained": False, "top3": ["SH-05", "SH-04", "SH-06"]}] * 30
    cand = [{"abstained": False, "top3": ["SH-01", "SH-02", "SH-03"]}] * 65 + [{"abstained": True, "top3": []}] * 35
    b, c = M.summarize(M.indicators(exp, base)), M.summarize(M.indicators(exp, cand))
    d = M.delta(b, c)
    assert d["top1_delta_pp"] == -5.0 and d["conditional_top1_delta_pp"] > 0
    assert d["top1_relative_change_pct"] == pytest.approx(-7.14, abs=0.01)  # relative ≠ pp


def test_paired_bootstrap_deterministic_and_brackets_delta():
    rng = np.random.default_rng(0)
    b = rng.random(200) < 0.6
    c = b.copy(); c[:20] = True
    lo, hi = M.paired_bootstrap_delta(b, c, 2000, 7, 0.95)
    assert (lo, hi) == M.paired_bootstrap_delta(b, c, 2000, 7, 0.95)
    d = (c.mean() - b.mean()) * 100
    assert lo <= d <= hi


def test_wilson_bounds():
    lo, hi = M.wilson(0, 10)
    assert lo == 0.0 and 0 < hi < 40
    assert M.wilson(0, 0) == (None, None)


def test_family_confusion_counts_abstain():
    cm = M.family_confusion(["SH-35", "SH-25"], [{"abstained": True, "top3": []}, {"abstained": False, "top3": ["SH-33", "SH-32", "SH-31"]}])
    assert cm["counts"]["Deep"]["ABSTAIN"] == 1 and cm["counts"]["Tan"]["Deep"] == 1


def test_secret_and_image_redaction():
    s = redact("key sk-ant-abcdefghijklmnop123 api_key=xyz email a.b@example.com data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA")
    assert "abcdefghijklmnop" not in s and "xyz" not in s and "example.com" not in s and "iVBORw0KGgoAAAANSUhEUg" not in s


@pytest.mark.parametrize("raw", ["not json", '{"summary": 5}', '{"highlights": []}', '{"summary": "x", "highlights": "nope", "unknowns": []}'])
def test_invalid_agent_json_rejected(raw):
    with pytest.raises(ValueError):
        parse_summary(raw)


def test_valid_agent_json_parsed():
    assert parse_summary('{"summary": "ok", "highlights": ["a"], "unknowns": []}').summary == "ok"


def test_favourable_summary_cannot_override_failed_gate():
    assert summary_contradicts("evaluation", "FAIL", "Great news: all gates pass and it is ready for release.")
    assert not summary_contradicts("evaluation", "PASS", "All gates pass.")
