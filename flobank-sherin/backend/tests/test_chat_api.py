"""Chat answers must match database records; every endpoint responds; streaming and history work."""
import json
import re

import pytest

from app.copilot import service as CP
from app.finance import engine as E
from tests.conftest import hdr


def ask(client, msg, **kw):
    r = client.post("/api/chat", json={"message": msg, **kw}, headers=hdr())
    assert r.status_code == 200, r.text
    return r.json()


EXPECTED = {
    "Sherin, how much money did you cost us this month?": "ai_cost",
    "How much revenue did FLO Bank generate?": "bank_revenue",
    "What is your net economic contribution?": "net_contribution",
    "Which agent is consuming the most tokens?": "tokens",
    "Show the most expensive Azure DevOps workflows.": "azure_expensive",
    "Compare your work against equivalent human effort.": "human_vs_ai",
    "Which portfolio investments require manager approval?": "approvals",
    "Show the last 30 days of AI costs and savings.": "last_n_days",
    "Why did our AI expenditure increase?": "why_spend",
    "How can we reduce operating costs without compromising quality?": "reduce_costs",
    "Why did Sherin spend more money today?": "why_spend",
}


@pytest.mark.parametrize("q,intent", EXPECTED.items())
def test_example_questions_route_and_link_to_dashboards(client, q, intent):
    r = ask(client, q)
    assert r["intent"] == intent
    assert r["links"] and all(l["route"].startswith("/") for l in r["links"])
    assert r["sources"]
    assert "synthetic demonstration data" in r["text"]


def test_ai_cost_answer_matches_kpi(client):
    k = {c["key"]: c for c in client.get("/api/finance/kpis").json()["cards"]}
    r = ask(client, "Sherin, how much money did you cost us this month?")
    assert CP.money(k["ai_cost"]["value"], "USD") in r["text"]
    pie = r["charts"][0]
    assert round(sum(pie["values"]), 2) == k["ai_cost"]["value"]


def test_revenue_answer_matches_ledger(client):
    k = {c["key"]: c for c in client.get("/api/finance/kpis").json()["cards"]}
    r = ask(client, "How much revenue did FLO Bank generate?")
    assert CP.money(k["bank_revenue"]["value"], "USD") in r["text"]
    assert CP.money(k["operating_profit"]["value"], "USD") in r["text"]


def test_net_contribution_matches_waterfall_in_inr(client):
    c = client.get("/api/finance/contribution", params={"currency": "INR"}).json()
    r = ask(client, "What is your net economic contribution?", currency="INR")
    assert CP.money(c["summary"]["net_benefit"], "INR") in r["text"] and "₹" in r["text"]
    assert r["charts"][0]["values"] == [w["value"] for w in c["waterfall"]]


def test_token_answer_names_top_agent(client):
    t = client.get("/api/finance/tokens").json()
    r = ask(client, "Which agent is consuming the most tokens?")
    assert t["per_agent"][0]["label"] in r["text"] and f"{t['per_agent'][0]['tokens']:,}" in r["text"]


def test_why_spend_today_uses_cost_records(client):
    r = ask(client, "Why did Sherin spend more money today?")
    assert "2026-10-31" in r["period"]["start"] and "per day" in r["text"].lower()
    d = client.get("/api/finance/cost-drivers", params={"period": "custom", "start": "2026-10-31", "end": "2026-10-31",
                                                        "baseline_start": "2026-10-24", "baseline_end": "2026-10-30"}).json()
    assert CP.money(d["total_per_day"]["current"], "USD") in r["text"]


def test_approval_answer_lists_guardian_decisions(client):
    r = ask(client, "Which portfolio investments require manager approval?")
    assert "TP-1002" in r["text"] and "BLOCK" in r["text"] and "TP-1005" in r["text"] and "INSUFFICIENT_DATA" in r["text"]
    assert isinstance(r["approvals"], list)


def test_guardian_specific_question(client):
    r = ask(client, "Why was TP-1002 blocked?")
    assert r["intent"] == "guardian" and "**BLOCK**" in r["text"] and "Restricted issuer" in r["text"]


def test_conversations_persist_and_search(client):
    r = ask(client, "How much revenue did FLO Bank generate?")
    cid = r["conversation_id"]
    r2 = ask(client, "What is your net economic contribution?", conversation_id=cid)
    assert r2["conversation_id"] == cid
    conv = client.get(f"/api/conversations/{cid}").json()
    assert [m["role"] for m in conv["messages"]] == ["user", "assistant", "user", "assistant"]
    assert conv["messages"][1]["payload"]["charts"]
    assert any(c["id"] == cid for c in client.get("/api/conversations", params={"q": "net economic"}).json())
    assert client.delete(f"/api/conversations/{cid}").status_code == 200
    assert client.get(f"/api/conversations/{cid}").status_code == 404


def test_stream_emits_activity_deltas_and_final(client):
    with client.stream("POST", "/api/chat/stream", json={"message": "What is your net economic contribution?"}, headers=hdr()) as r:
        body = "".join(r.iter_text())
    events = re.findall(r"event: (\w+)", body)
    assert events[0] == "activity" and "delta" in events and events[-2:] == ["final", "done"]
    final = json.loads(re.search(r"event: final\ndata: (.*)\n", body).group(1))
    deltas = "".join(json.loads(d) for d in re.findall(r"event: delta\ndata: (.*)\n", body))
    assert deltas == final["text"]


def test_chat_attachment_starts_agent_run(client):
    r = ask(client, "Please debug this", attachments=[{"name": "x.py", "content": "def f(:\n  pass\n"}])
    assert r["intent"] == "harness" and r["run_id"]
    run = client.get(f"/api/harness/runs/{r['run_id']}").json()
    assert run["result"]["steps"][0]["output"]["syntax_error"]["line"] == 1


def test_unknown_question_without_llm_is_honest(client):
    r = ask(client, "What colour is the sky on Mars?")
    assert r["intent"] == "general" and "not available" in r["text"]


GETS = ["/api/health", "/api/meta", "/api/finance/kpis", "/api/finance/revenue-expenditure", "/api/finance/contribution", "/api/finance/human-vs-ai",
        "/api/finance/ai-costs", "/api/finance/tokens", "/api/finance/forecast", "/api/finance/agents", "/api/finance/departments",
        "/api/finance/cost-drivers", "/api/finance/reconciliation", "/api/fx/rates", "/api/baselines", "/api/portfolios", "/api/portfolios/PF-BAL",
        "/api/guardian/graph", "/api/guardian/proposals", "/api/approvals", "/api/harness/graph", "/api/harness/runs", "/api/harness/agents",
        "/api/engineering/workflows", "/api/engineering/workflows?department=python_engineering", "/api/engineering/incidents", "/api/compliance/events",
        "/api/metrics/live", "/api/metrics/history?period=ttm", "/api/metrics/alerts", "/api/audit", "/api/conversations"]


@pytest.mark.parametrize("url", GETS)
def test_get_endpoints(client, url):
    assert client.get(url).status_code == 200


def test_reports_download(client):
    md = client.get("/api/reports/executive", params={"currency": "CAD"})
    assert md.status_code == 200 and "attachment" in md.headers["content-disposition"] and "SYNTHETIC" in md.text and "PASS - Net benefit identity" in md.text
    csv = client.get("/api/reports/executive", params={"format": "csv"})
    assert csv.text.startswith("metric,value") and "Total Bank Revenue" in csv.text


def test_live_metrics_are_measured(client):
    m = client.get("/api/metrics/live").json()
    assert m["data_class"] == "measured" and m["requests"] > 0 and m["p95_ms"] is not None
    assert "gpu" in m["host"]


def test_engineering_cost_sentence(client):
    w = client.get("/api/engineering/workflows").json()["workflows"][0]
    assert "minutes of agent execution" in w["sentence"] and "human baseline" in w["sentence"]


def test_bad_inputs(client):
    assert client.get("/api/finance/kpis", params={"currency": "EUR"}).status_code == 400
    assert client.get("/api/finance/kpis", params={"dc": "real"}).status_code == 400
    assert client.get("/api/finance/kpis/bogus").status_code == 404
