"""Enterprise domains and Ask Copilot: deterministic data, measured figures, grounded answers."""

from __future__ import annotations

import re

import pytest

from app.copilot import engine
from app.copilot.router import parse
from app.enterprise import data, queries

from conftest import user


@pytest.fixture()
def enterprise(platform):
    data.seed()
    return platform


def test_seed_is_deterministic(enterprise):
    first = data.generate_sales()
    assert first == data.generate_sales()
    assert len(first) == 16 * 6 * 6 * 3  # weeks × products × regions × channels


def test_campaign_uplift_is_measured_from_sales(enterprise):
    perf = {c["id"]: c for c in queries.campaign_performance()["campaigns"]}
    multibuy = perf["CMP-2026-08-QC-3FOR2"]
    assert multibuy["unit_uplift_pct"] > 25  # generator effect is +42%, measured with noise and seasonality
    coldbrew = perf["CMP-2026-09-ON-COLDBREW"]
    assert coldbrew["unit_uplift_pct"] > 0 > coldbrew["revenue_change_pct"]  # discount outweighs volume


def test_inventory_flags_campaign_stock_risk(enterprise):
    inv = queries.inventory_status()
    critical = {(a["warehouse"], a["sku"]) for a in inv["alerts"] if a["status"] == "critical"}
    assert ("DC-TOR", "FS-APPLE-355") in critical
    risk = {x["sku"]: x for x in queries.campaign_stock_risk()["lines"]}
    assert risk["FS-APPLE-355"]["risk"] == "high" and risk["FS-APPLE-355"]["stockout_before_start"]
    assert risk["FS-MANGO-355"]["risk"] == "low"


def test_compliance_finds_seeded_listing_issues(enterprise):
    result = queries.compliance_check()
    assert result["listings_checked"] == 18
    found = {(i["sku"], i["channel"], i["severity"], i["rule"]) for i in result["issues"]}
    assert ("NT-OATMILK-1L", "retail", "critical", "allergen statement") in found
    assert ("BH-COLDBREW-300", "marketplace", "warning", "record version") in found
    assert result["critical"] == 1


@pytest.mark.parametrize(("question", "intents", "entities"), [
    ("Is there enough apple stock for the Ontario weekend campaign?", ["campaign", "inventory"],
     {"skus": ["FS-APPLE-355"], "provinces": ["ON"]}),
    ("Top selling products in Quebec last 8 weeks", ["sales"], {"provinces": ["QC"], "weeks": 8}),
    ("Which products are running low in Vancouver?", ["inventory"], {"warehouses": ["DC-VAN"]}),
    ("What is the latest status of the release?", ["delivery"], {}),
    ("What is the weather in Paris?", [], {}),
])
def test_router_extracts_intents_and_entities(question, intents, entities):
    parsed = parse(question)
    assert parsed.intents == intents
    for key, value in entities.items():
        assert parsed.entities()[key] == value


def _cited_ids(answer: dict) -> set[str]:
    return set(re.findall(r"\[(S\d+)\]", answer["answer"]))


@pytest.mark.parametrize("question", [
    "Give me a briefing",
    "How did our sales do in the last 4 weeks?",
    "Is there enough apple stock for the Ontario weekend campaign?",
    "Which listings have allergen issues?",
    "How did past promotions perform?",
    "What does the returns policy say about partial returns?",
])
def test_answers_cite_only_sources_they_return(enterprise, question):
    answer = engine.ask(question, user("val.viewer"))
    assert answer["answered"] and answer["mode"] == "demo" and answer["provenance"] == "deterministic"
    cited = _cited_ids(answer)
    assert cited, "every answer must cite at least one source"
    assert cited <= {s["id"] for s in answer["sources"]}
    assert answer["tool_calls"], "answers come from read-only tool calls"


def test_answer_numbers_match_the_queries(enterprise):
    answer = engine.ask("How did our sales do in the last 4 weeks?", user("val.viewer"))
    expected = queries.sales_summary(4)
    assert engine.money(expected["revenue_cents"]) in answer["answer"]
    assert engine.pct(expected["revenue_change_pct"]) in answer["answer"]


def test_out_of_scope_questions_are_not_answered(enterprise):
    answer = engine.ask("What is the weather in Paris?", user("val.viewer"))
    assert not answer["answered"] and answer["sources"] == []
    assert "can't answer" in answer["answer"]


def test_copilot_is_read_only(enterprise):
    answer = engine.ask("Approve the release", user("rina.release"))
    assert answer["answer"].startswith("I'm read-only")
    assert not [t for t in answer["tool_calls"] if not t["tool"].startswith(
        ("evaluate", "get", "sales", "campaign", "inventory", "compliance", "product", "live", "search", "executive"))]


def test_live_mode_without_credentials_is_labelled(enterprise):
    answer = engine.ask("Give me a briefing", user("val.viewer"), mode="live")
    assert answer["mode"] == "demo" and "LIVE mode is not configured" in answer["notice"]


def test_conversation_is_recorded(enterprise):
    first = engine.ask("Give me a briefing", user("val.viewer"))
    engine.ask("Which listings have allergen issues?", user("val.viewer"), first["conversation_id"])
    history = engine.history(first["conversation_id"])
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
