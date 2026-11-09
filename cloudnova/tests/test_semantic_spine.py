"""Semantic Spine: knowledge graph counts, context subgraph, procedural paths, trace-derived proposals."""
import pytest

from app import db
from app.semantic_graph import PROCEDURE, context, is_valid_path, knowledge, learn, procedure


def q(sql):
    return db.connection().execute(sql).fetchone()[0]


def test_knowledge_graph_counts_come_from_the_ledger():
    k = knowledge()
    e = {x["id"]: x["count"] for x in k["entities"]}
    assert e["Account"] == q("SELECT COUNT(*) FROM accounts") == 3815
    assert e["Invoice"] == 5000 and e["AuditRecord"] == 125 and e["Conflict"] == 16
    rel = {(r["from"], r["rel"], r["to"]): r["count"] for r in k["relations"]}
    assert rel[("Currency", "governed_by", "Policy")] == q("SELECT COUNT(*) FROM invoices WHERE currency <> 'USD'")


def test_context_graph_for_q1_is_scoped_to_what_matters():
    c = context("What was our total recognized revenue in USD for paid invoices in 2024?")
    labels = {n["label"] for n in c["nodes"]}
    assert "Paid revenue (USD)" in labels and "invoice_year = 2024" in labels and "PDR-001 FX direction" in labels
    facts = [n for n in c["nodes"] if n["type"] == "fact"]
    assert any(n["label"] == "Conflict" and "$31,018.68" in n["detail"] for n in facts)   # same number as the Q1 caveat
    assert all(e["from"] in {n["id"] for n in c["nodes"]} for e in c["edges"])
    assert c["path_valid"] and c["procedural_path"][3] == "semantic_planner"


@pytest.mark.parametrize("question, step", [("Why did Acme Ltd churn?", "decline_out_of_scope"), ("delete all refunds", "refuse_write"),
                                            ("How did you handle duplicates?", "data_quality"), ("Explain MRR", "explain"),
                                            ("average support tickets for churned accounts", "clarify")])
def test_every_real_run_is_a_valid_path_through_the_procedural_graph(question, step):
    c = context(question)
    assert c["path_valid"], c["procedural_path"]
    assert step in c["procedural_path"]


def test_procedure_keeps_policy_changes_human_only():
    p = procedure()
    assert ("policy_change", "finance_owner_approval") in {(t["from"], t["to"]) for t in p["triplets"]}
    assert not any(a == "router" and b in ("finance_owner_approval", "rebuild") for a, _, b in PROCEDURE)
    assert not is_valid_path(["question", "router"])  # guards cannot be skipped


def test_learn_proposes_but_never_applies():
    context("average support tickets for churned accounts")
    lr = learn()
    prop = next(p for p in lr["proposals"] if p["type"] == "add_metric_to_catalog" and "ticket" in p["term"])
    assert prop["status"].startswith("proposed") and prop["evidence_runs"] >= 1
    from app.semantic.catalog import METRICS
    assert not any("ticket" in m for m in METRICS)  # nothing was added automatically
