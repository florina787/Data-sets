"""Every bundled scenario produces its documented expected outcome."""

from __future__ import annotations

import pytest

from app.scenarios import list_scenarios

SCENARIOS = list_scenarios()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario_expected_outcome(scenario, assess):
    r = assess(scenario["id"])
    exp = scenario["expected"]
    d = r.decision
    assert d.primary_architecture.value == exp["primary_architecture"]
    assert d.ai_recommended == exp["ai_recommended"]
    if "agentic_verdict" in exp:
        assert d.agentic_verdict.value == exp["agentic_verdict"]
    for flag in ("citations_mandatory", "human_review_mandatory", "requires_human_approval"):
        if flag in exp:
            assert getattr(d, flag) == exp[flag]
    if "roi_verdict" in exp:
        assert r.roi.verdict.value == exp["roi_verdict"]


def test_scenarios_are_fictional():
    assert len(SCENARIOS) >= 5
    for s in SCENARIOS:
        assert "fictional" in s["disclaimer"].lower()


def test_minimum_required_scenarios_present():
    ids = {s["id"] for s in SCENARIOS}
    assert {"banking-transaction-rules", "banking-policy-knowledge", "retail-customer-service", "legal-research", "finops-incident-investigation"} <= ids
