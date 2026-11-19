"""FLOW WEALTH through the real FLO conversation API, on the real Kaggle research lake (skipped when the lake is absent)."""
import pytest
from fastapi.testclient import TestClient

from conversation.schemas import MessageResponse
from markets import service as S

pytestmark = [pytest.mark.critical,
              pytest.mark.skipif(not S.available(), reason="real Kaggle market lake not built here (python -m markets.ingest; markets.lake; markets.features)")]


@pytest.fixture(scope="module")
def client(st):
    from backend.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def ask(client):
    tokens = {}

    def make(user):
        if user not in tokens:
            tokens[user] = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"user_id": user}).json()["access_token"]}
        cid = client.post("/api/conversations", json={"persona": None}, headers=tokens[user]).json()["id"]

        def say(text):
            r = client.post(f"/api/conversations/{cid}/messages", json={"text": text, "context": {}}, headers=tokens[user])
            assert r.status_code == 200, r.text
            d = r.json()
            MessageResponse.model_validate(d)
            return d
        return say
    return make


def test_single_stock_is_grounded_historical_and_not_synthetic(ask):
    d = ask("u-cio")("Analyze Apple's historical performance.")
    assert d["status"] == "complete" and d["intent"]["intent"] == "market_security" and d["intent"]["entities"]["tickers"] == ["AAPL"]
    assert {"market_price_history", "market_drawdown"} <= {c["chart_id"] for c in d["charts"]}
    for c in d["charts"]:
        if c["chart_id"] != "agent_graph":
            assert c["provenance"] == "historical_market_data" and c["lineage"]["synthetic"] is False
    assert d["data_freshness"]["synthetic"] is False and d["data_freshness"]["as_of"] == "2017-11-10"
    assert "not current prices" in d["answer"]["body"]
    assert d["recommendations"] == []          # no trading recommendations, ever
    lims = [i["title"] for i in d["insights"] if i["section"] == "limitation"]
    assert any("survivorship" in x.lower() for x in lims) and any("NO VALIDATED TRADING EDGE" in x for x in lims)


def test_compare_two_stocks_with_period(ask):
    d = ask("u-analyst")("Compare Microsoft and Nvidia from 2014 to 2016.")
    assert d["intent"]["intent"] == "market_compare" and d["intent"]["entities"]["tickers"] == ["MSFT", "NVDA"]
    assert "NVDA" in d["answer"]["headline"] and "2016-12-30" in d["answer"]["headline"]


def test_model_accuracy_reports_no_validated_edge(ask):
    d = ask("u-cio")("Show model accuracy over the holdout period.")
    assert d["status"] == "complete" and "NO VALIDATED TRADING EDGE" in d["answer"]["headline"]
    assert {"model_holdout_equity", "model_comparison"} <= {c["chart_id"] for c in d["charts"]}
    assert any(t["table_id"] == "promotion_decisions" for t in d["tables"])
    assert all(c["provenance"] == "research_result" for c in d["charts"] if c["chart_id"].startswith("model_"))


def test_rejection_reasons_cite_costs(ask):
    d = ask("u-cio")("Why did the model reject this opportunity?")
    assert d["intent"]["intent"] == "model_rejection" and "after costs" in d["answer"]["body"]


def test_bull_bear_is_balanced_cited_and_follow_up_keeps_ticker(ask):
    say = ask("u-cio")
    say("Analyze NVDA stock.")
    d = say("What about the bear case?")
    assert d["intent"]["intent"] == "bull_bear" and d["intent"]["entities"]["tickers"] == ["NVDA"]
    assert "bull points" in d["answer"]["headline"] and "bear points" in d["answer"]["headline"]
    claims = next(t for t in d["tables"] if t["table_id"] == "evidence_claims")
    assert {r[0] for r in claims["rows"]} >= {"Bull", "Skeptic"} and all(r[2] for r in claims["rows"])   # every claim cites evidence
    assert any(t["table_id"] == "risk_checks" for t in d["tables"])


def test_regime_overview_and_datasets(ask):
    say = ask("u-cio")
    r = say("Explain the latest available market regime.")
    assert r["status"] == "complete" and "historical" in r["answer"]["headline"]
    o = say("Show the market overview.")
    assert o["intent"]["intent"] == "market_overview" and "not today" in o["answer"]["headline"]
    ds = say("Which datasets are available?")
    assert ds["status"] == "complete" and "Kaggle" in ds["answer"]["headline"]


def test_public_data_for_prospect_but_not_model_research(ask):
    p = ask("u-prospect")
    assert p("Analyze Apple's historical performance.")["status"] == "complete"
    d = p("Show model accuracy over the holdout period.")
    assert d["status"] == "denied" and d["charts"] == []


def test_identity_without_market_permission_is_denied(ask):
    d = ask("u-compliance")("Analyze Apple's historical performance.")
    assert d["status"] == "denied" and not [c for c in d["charts"] if c["chart_id"] != "agent_graph"]


def test_enterprise_questions_are_not_hijacked_by_ticker_lookalikes(ask):
    say = ask("u-ceo")
    assert say("Why is our AUM growing while profitability declines?")["intent"]["intent"] == "aum_profitability"
    assert say("Identify opportunities to improve revenue.")["intent"]["intent"] == "revenue_opportunities"
