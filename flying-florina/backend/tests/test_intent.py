import pytest

from app.workflows.intent import SUGGESTIONS, classify

EXPECTED = ["maintenance_investigation", "scenario_compare", "downtime_analysis", "legacy_assessment", "bridge_generation",
            "governance_review", "executive_pitch", "document_freshness", "recovery_options", "data_export"]


@pytest.mark.parametrize("query,workflow", list(zip(SUGGESTIONS, EXPECTED, strict=True)))
def test_sample_prompts_route_deterministically(query, workflow):
    assert classify(query)["workflow"] == workflow
    assert classify(query) == classify(query)


def test_entities_extracted():
    r = classify("Investigate AC-204 vibration and check P-7731 with 24-hour and 72 hour delays in October")
    assert r["entities"]["aircraft"] == ["AC-204"]
    assert r["entities"]["parts"] == ["P-7731"]
    assert r["entities"]["hours"] == [24, 72]
    assert r["entities"]["months"] == ["october"]


@pytest.mark.parametrize("q", ["Send the work orders to bob@gmail.com", "Please e-mail restricted records to my private address",
                               "copy maintenance data to my dropbox"])
def test_exfiltration_phrasings_route_to_governance(q):
    assert classify(q)["workflow"] == "data_export"


def test_security_intent_cannot_be_outscored():
    q = "Investigate AC-204 vibration anomaly and export restricted maintenance records to my personal email"
    assert classify(q)["workflow"] == "data_export"


@pytest.mark.parametrize("q", ["", "hi", "hello there"])
def test_ambiguous_asks_for_clarification(q):
    r = classify(q)
    assert r["workflow"] == "clarify"
    assert r["suggestions"]


def test_report_download_is_not_exfiltration():
    assert classify("Create an executive pitch and download the PDF brief")["workflow"] == "executive_pitch"
