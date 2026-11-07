"""Financial Investigation Studio: graph lineage, invoice reconciliation, policy impact, consistency with answers."""
import pytest
from fastapi.testclient import TestClient

from app import db
from app.api import app
from app.errors import AppError
from app.studio import DISCREPANCIES, butterfly, graph, replay


def q(sql, p=None):
    return db.connection().execute(sql, p or []).fetchall()


def test_graph_lineage_every_edge_is_a_database_fact():
    g = graph(accounts=15)
    ids = {n["id"] for n in g["nodes"]}
    assert all(e["from"] in ids and e["to"] in ids for e in g["edges"])
    for e in g["edges"]:
        a, b = e["from"].split(":", 1)[1], e["to"].split(":", 1)[1]
        if e["type"] == "billed":
            assert q("SELECT account_id FROM invoices WHERE invoice_id=?", [b])[0][0] == a
        elif e["type"] == "flagged_by":
            assert q(f"SELECT COUNT(*) FROM invoices i WHERE i.invoice_id=? AND {DISCREPANCIES[b][1]}", [a])[0][0] == 1
        elif e["type"] == "governed_by":
            assert q("SELECT currency FROM invoices WHERE invoice_id=?", [a])[0][0] != "USD"
        elif e["type"] == "resolved_by":
            assert "dedup_conflict" in q("SELECT dq_flags FROM invoices WHERE invoice_id=?", [a])[0][0]
        elif e["type"] == "identity_question":
            assert q("SELECT COUNT(DISTINCT account_name) FROM invoices WHERE account_id=?", [a])[0][0] > 1
    top = [n["ref"] for n in g["nodes"] if n["type"] == "account"][:5]
    assert top == ["ACC-7509", "ACC-1420", "ACC-9946", "ACC-1196", "ACC-5211"]  # same as Q5


def test_graph_filters_and_search():
    g = graph(q="INV-102104")
    assert any(n["ref"] == "INV-102104" for n in g["nodes"])
    g = graph(flag="status_conflict", accounts=40)
    assert any(e["type"] == "flagged_by" and e["to"] == "disc:status_conflict" for e in g["edges"])
    assert graph(region="EMEA")["nodes"][0]["region"] == "EMEA"
    with pytest.raises(AppError):
        graph(flag="made_up")


def test_replay_conflict_invoice_reconciles_and_reproduces():
    r = replay("INV-102104")
    st = {s["step"]: s for s in r["steps"]}
    assert len(st["Imported"]["evidence"]["raw_rows"]) == 2
    assert all(n["reproduced"] for n in st["Normalized"]["evidence"])
    rec = st["Reconciled"]["evidence"]
    assert rec["dedup_rule"] == "conflict_precedence" and rec["conflict"]["winner"] == "paid"
    assert rec["rejected"] == [{"raw_row_number": 4296, "reason": "lost_conflict", "status": "failed"}]
    calc = st["Calculated"]["evidence"]
    assert calc["expected_usd"] == 49000.0 and calc["matches_price_book"]["documented"]
    assert st["Evaluated"]["evidence"]["oracle"]["agrees"]
    assert r["evidence_hash"] == replay("INV-102104")["evidence_hash"]  # deterministic


def test_replay_eur_invoice_shows_fx_evidence():
    r = replay("INV-100012")
    calc = {s["step"]: s for s in r["steps"]}["Calculated"]["evidence"]
    assert calc["fx"]["documented"] == pytest.approx(5715.36) and calc["fx"]["inverse"] == pytest.approx(4900.0)
    assert calc["matches_price_book"] == {"documented": False, "inverse": True}


@pytest.mark.parametrize("bad", ["", "x" * 50, "INV-1;DROP"])
def test_replay_rejects_bad_ids(bad):
    with pytest.raises(AppError):
        replay(bad)


def test_replay_unknown_invoice_404():
    with pytest.raises(AppError) as e:
        replay("INV-999999")
    assert e.value.code == "not_found"


def test_butterfly_consistent_with_answers_and_never_claims_approval():
    b = butterfly("fx_direction")
    cur = next(i for i in b["interpretations"] if i["value"] == "documented")
    alt = next(i for i in b["interpretations"] if i["value"] == "inverse")
    m = {x["metric"]: x["value"] for x in cur["metrics"]}
    assert m["Q1 · paid revenue 2024"] == pytest.approx(32686371.16) and m["Q3 · refunds"] == pytest.approx(-8925163.80)
    assert m["Q6 · pending/failed exposure"] == pytest.approx(28983255.91)
    assert {x["metric"]: x["value"] for x in alt["metrics"]}["Q1 · paid revenue 2024"] == pytest.approx(29595624.38)
    assert cur["status"].startswith("active") and alt["status"] == "proposed — not approved"
    assert cur["top5"] == ["ACC-7509", "ACC-1420", "ACC-9946", "ACC-1196", "ACC-5211"]
    ident = butterfly("account_identity")
    base = next(i for i in ident["interpretations"] if i["value"] == "account_id")
    assert base["top_region"] == "APAC" and {x["metric"]: x["value"] for x in base["metrics"]}["Q4 · Enterprise churn"] == pytest.approx(0.21923, abs=1e-5)
    assert next(i for i in ident["interpretations"] if i["value"] == "account_name")["status"].startswith("proposed — blocked")


def test_studio_endpoints():
    c = TestClient(app)
    assert c.get("/api/v1/studio/graph?accounts=5").json()["counts"]["accounts"] == 5
    assert c.get("/api/v1/studio/invoices/INV-102104/replay").status_code == 200
    assert c.get("/api/v1/studio/invoices/INV-999999/replay").status_code == 404
    assert c.get("/api/v1/studio/policies/fx_direction/impact").status_code == 200
    assert c.get("/api/v1/studio/policies/nope/impact").status_code == 404
