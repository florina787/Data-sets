import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.api import app
from app.errors import AppError
from app.reconciliation import reconciliation
from app.sources.base import RAW_CONTRACT_COLUMNS, CsvLedgerAdapter


def test_reconciliation_accounts_for_every_row_and_dollar():
    r = reconciliation()
    assert r["raw_rows"] == 5125 and r["clean_invoices"] == 5000 and r["rejected_rows"] == 125
    assert sum(s["rows"] for s in r["waterfall"] if s["kind"] == "delta") == -125
    assert {b["reason"]: b["rows"] for b in r["by_reason"]} == {"exact_duplicate": 82, "synonym_duplicate": 27, "lost_conflict": 16}
    im = r["impact"]["paid_revenue"]
    assert im["naive_no_dedup"] - im["clean"] == pytest.approx(im["overstatement_avoided"])
    assert im["overstatement_avoided"] > 0
    assert r["conflicts"]["count"] == 16 and len(r["conflicts"]["rows"]) == 16


def test_csv_adapter_enforces_raw_contract(tmp_path):
    good = CsvLedgerAdapter("data/raw/cloudnova_invoices.csv").extract()
    assert list(good.rows.columns) == RAW_CONTRACT_COLUMNS and good.provenance["rows"] == 5125
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"invoice_id": ["INV-1"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="raw contract"):
        CsvLedgerAdapter(bad).extract()


def test_v1_api_contract():
    c = TestClient(app)
    paths = c.get("/openapi.json").json()["paths"]
    assert all(p.startswith("/api/v1/") for p in paths)
    assert c.get("/api/v1/reconciliation").json()["clean_invoices"] == 5000
    assert any(m["id"] == "net_revenue" for m in c.get("/api/v1/metrics").json()["metrics"])
    assert c.get("/api/v1/sources").json()["active"][0]["adapter"] == "csv_ledger"
    bad = c.post("/api/v1/ask", json={"question": "x" * 1001})
    assert bad.status_code == 422
    assert c.post("/api/v1/ask", json={"question": "hi", "session_id": "../etc"}).status_code == 422


def test_reconciliation_question_routes_to_data_quality():
    from app.agent import supervisor
    r = supervisor.ask("Reconcile the 5,125 raw rows to the clean invoices")
    assert r["intent"] == "data_quality" and "5,000" in r["answer"] and "overstatement" in r["answer"]


def test_llm_only_mode_requires_qwen(monkeypatch):
    from app.agent import supervisor
    from app.config import get_settings
    monkeypatch.setenv("QUERY_MODE", "llm")
    get_settings.cache_clear()
    try:
        with pytest.raises(AppError) as e:
            supervisor.ask("How much have we given back in refunds?")
        assert e.value.code == "llm_unavailable"
    finally:
        monkeypatch.delenv("QUERY_MODE")
        get_settings.cache_clear()
