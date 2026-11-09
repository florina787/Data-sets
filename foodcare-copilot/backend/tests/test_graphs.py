"""Knowledge, context and procedural graphs and agent activity come from stored records."""

from __future__ import annotations

from app import graphs
from app.copilot import engine
from app.enterprise import data
from app.vision import service, synthetic

from conftest import user


def _batch(seed: int = 1) -> dict:
    b = service.create_batch("val.viewer", "graph test", supplier="Synthetic farm A")
    return service.add_image(b["id"], "val.viewer", synthetic.render(seed=seed)[0], "s.png")["batch"]


def test_knowledge_graph_reflects_the_databases(platform):
    data.seed()
    k = graphs.knowledge("val.viewer")
    types = {n["type"] for n in k["nodes"]}
    assert {"product", "warehouse", "campaign", "policy", "model"} <= types
    assert any(e["relation"] == "stocked at" for e in k["edges"])
    ids = {n["id"] for n in k["nodes"]}
    assert all(e["source"] in ids and e["target"] in ids for e in k["edges"])
    assert not any(n["type"] == "inspection" for n in k["nodes"])  # no batches yet
    b = _batch()
    k2 = graphs.knowledge("val.viewer")
    assert f"batch:{b['id']}" in {n["id"] for n in k2["nodes"]}
    assert {"source": f"batch:{b['id']}", "target": "supplier:Synthetic farm A", "relation": "supplied by"} \
        in k2["edges"]
    assert not any(n["type"] == "inspection" for n in graphs.knowledge("maya.marketing")["nodes"])


def test_context_graph_is_the_scoped_subgraph_of_a_real_answer(platform):
    data.seed()
    assert graphs.context("val.viewer")["run"] is None
    a = engine.ask("Is there enough apple stock for the Ontario weekend campaign?", user("val.viewer"))
    c = graphs.context("val.viewer")
    assert c["run"]["question"].startswith("Is there enough apple stock")
    kinds = {n["type"] for n in c["nodes"]}
    assert {"question", "intent", "entity", "tool", "source"} <= kinds
    assert [n["label"] for n in c["nodes"] if n["type"] == "tool"] == [t["tool"] for t in a["tool_calls"]]
    assert "product:FS-APPLE-355" in c["scope"]["knowledge_nodes"]
    assert c["runs"][0]["id"] == a["agent_run_id"]
    assert graphs.context("maya.marketing")["run"] is None  # private per user


def test_procedural_graph_counts_and_routes_rejection_through_approval(platform):
    b = _batch()
    p = graphs.procedure("val.viewer")
    counts = {n["id"]: n["count"] for n in p["nodes"]}
    assert counts["detect"] == 12 and counts["accept"] == b["summary"]["counts"]["Good"]
    assert counts["reject"] == b["summary"]["counts"]["Not Good"] == counts["approval"]
    assert {"source": "reject", "target": "approval", "relation": "always"} in p["edges"]
    bad = next(x for x in b["potatoes"] if x["grade"] == "Not Good")
    service.correct_potato(b["id"], "val.viewer", bad["potato_no"], "Good", "soil, not rot")
    counts2 = {n["id"]: n["count"] for n in graphs.procedure("val.viewer")["nodes"]}
    assert counts2["correct"] == 1 and counts2["approval"] == counts["approval"] - 1


def test_agent_activity_lists_runs_with_timed_tools(platform):
    data.seed()
    _batch()
    engine.ask("Which listings have allergen issues?", user("val.viewer"))
    act = graphs.activity()
    agents = {a["agent"]: a for a in act["agents"]}
    assert {"vision.agent", "copilot.supervisor"} <= set(agents)
    assert all(r["tool_calls"] for r in act["runs"])
    assert any(t["tool"] == "detect_potatoes" for t in act["tools"])
