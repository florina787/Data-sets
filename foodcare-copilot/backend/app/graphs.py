"""Knowledge, context and procedural graphs, and agent activity, built from stored records.

* Knowledge graph ("what is true"): entities in the databases and their relations.
* Context graph ("what matters now"): the scoped subgraph one agent run actually used:
  the question, the entities it resolved, the tools it called and the sources it cited.
  The supervisor records it with every answer (``agent_runs.detail.context``).
* Procedural graph ("what do I do next"): the potato-quality procedure as explicit steps
  and transitions, with live counts. Rejection always routes through human approval.
* Agent activity: recorded agent runs and their timed tool calls.
Nothing here is simulated; empty data gives an empty graph.
"""

from __future__ import annotations

import json

from app.db import rows
from app.memory.store import get_store

PROCEDURE_NODES = [
    ("inspect", "Inspect image", "vision"), ("detect", "Detect & number potatoes", "vision"),
    ("grade", "Grade with thresholds", "rules"), ("accept", "Accept (Good)", "outcome"),
    ("review", "Inspector review (Moderate)", "human"), ("reject", "Reject candidate (Not Good)", "decision"),
    ("approval", "Human approval required", "human"), ("reimage", "Re-image (not graded)", "outcome"),
    ("correct", "Correction recorded", "human"), ("learn", "Trace & learn", "learning"),
]
PROCEDURE_EDGES = [
    ("inspect", "detect", "image accepted"), ("detect", "grade", "regions measured"),
    ("grade", "accept", "all checks Good"), ("grade", "review", "Moderate"), ("grade", "reject", "Not Good"),
    ("grade", "reimage", "edge or touching"), ("reject", "approval", "always"),
    ("review", "correct", "if inspector disagrees"),
    ("approval", "correct", "decision with reason"), ("correct", "learn", "labelled example"),
    ("accept", "learn", "trace"),
]


def _node(nid: str, kind: str, label: str, **extra) -> dict:
    return {"id": nid, "type": kind, "label": label, **extra}


def knowledge(username: str) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def add(n: dict) -> None:
        nodes.setdefault(n["id"], n)

    for p in rows("SELECT sku, name, category FROM ent_products"):
        add(_node(f"product:{p['sku']}", "product", p["name"], detail=p["category"]))
    for w in rows("SELECT id, name FROM ent_warehouses"):
        add(_node(f"warehouse:{w['id']}", "warehouse", w["id"], detail=w["name"]))
    for s in rows("SELECT warehouse, sku, on_hand FROM ent_stock"):
        edges.append({"source": f"product:{s['sku']}", "target": f"warehouse:{s['warehouse']}",
                      "relation": "stocked at", "detail": f"{s['on_hand']:,} on hand"})
    for c in rows("SELECT id, name, region, skus_json FROM ent_campaigns"):
        add(_node(f"campaign:{c['id']}", "campaign", c["name"], detail=c["region"]))
        for sku in json.loads(c["skus_json"]):
            edges.append({"source": f"campaign:{c['id']}", "target": f"product:{sku}", "relation": "promotes"})
    from app.ml import registry

    registry.ensure_builtins()
    store = get_store()
    batches = store.query("SELECT id, title, supplier, summary_json FROM inspection_batches WHERE username = ?"
                          " ORDER BY created_at DESC LIMIT 8", (username,))
    for b in batches:
        s = json.loads(b["summary_json"] or "{}")
        add(_node(f"batch:{b['id']}", "inspection", b["id"],
                  detail=f"{s.get('detected', 0)} potatoes, {s.get('counts', {}).get('Not Good', 0)} Not Good"))
        if b["supplier"]:
            add(_node(f"supplier:{b['supplier']}", "supplier", b["supplier"]))
            edges.append({"source": f"batch:{b['id']}", "target": f"supplier:{b['supplier']}",
                          "relation": "supplied by"})
    try:
        from app.tools.retrieval import get_index

        for d in get_index().documents():
            add(_node(f"policy:{d['doc_id']}", "policy", d["doc_id"], detail=f"{d['title']} v{d['version']}"))
    except Exception:  # noqa: BLE001 - the graph still works without the document index
        pass
    for m in store.query("SELECT id, kind, trained FROM ml_models WHERE status = 'active'"):
        add(_node(f"model:{m['id']}", "model", m["id"].split("@")[0],
                  detail=f"{m['kind']}, {'trained' if m['trained'] else 'not trained'}"))
    for e in store.query("SELECT DISTINCT model_id, dataset_id FROM ml_evaluations"):
        add(_node(f"dataset:{e['dataset_id']}", "dataset", e["dataset_id"].split("@")[0]))
        if f"model:{e['model_id']}" in nodes:
            edges.append({"source": f"model:{e['model_id']}", "target": f"dataset:{e['dataset_id']}",
                          "relation": "evaluated on"})
    for b in batches:  # the detector produced every stored batch
        edges.append({"source": f"batch:{b['id']}", "target": "model:potato-detector-classical@1.0",
                      "relation": "inspected by"})
    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    degree: dict[str, int] = {}
    for e in edges:
        degree[e["source"]] = degree.get(e["source"], 0) + 1
        degree[e["target"]] = degree.get(e["target"], 0) + 1
    for n in nodes.values():
        n["degree"] = degree.get(n["id"], 0)
    return {"nodes": list(nodes.values()), "edges": edges}


def scope(entities: dict, intents: list[str], sources: list[dict]) -> dict:
    """Knowledge-graph nodes and procedure steps an answer used (stored with each agent run)."""
    ids = [f"product:{s}" for s in entities.get("skus", [])]
    ids += [f"warehouse:{w}" for w in entities.get("warehouses", [])]
    if entities.get("batch_id"):
        ids.append(f"batch:{entities['batch_id']}")
    for s in sources:
        ref = s.get("ref", "")
        if ref.startswith("inspection_batches:"):
            ids.append(f"batch:{ref.split(':', 1)[1]}")
        elif s.get("kind") == "document":
            ids.append(f"policy:{ref.split(' ')[0]}")
    steps = []
    if "inspection" in intents:
        steps = (["grade", "review", "reject", "approval"] if entities.get("potato_no")
                 else ["inspect", "detect", "grade"])
    return {"knowledge_nodes": sorted(set(ids)), "procedure_steps": steps}


def context(username: str, agent_run_id: str | None = None) -> dict:
    """The context graph of one copilot run (default: the user's latest)."""
    store = get_store()
    runs = store.query("SELECT * FROM agent_runs WHERE agent = 'copilot.supervisor' AND"
                       " json_extract(detail_json, '$.username') = ? ORDER BY started_at DESC LIMIT 30", (username,))
    choices = [{"id": r["id"], "question": r["input_summary"], "started_at": r["started_at"]} for r in runs]
    run = next((r for r in runs if r["id"] == agent_run_id), runs[0] if runs else None)
    if not run:
        return {"runs": choices, "run": None, "nodes": [], "edges": []}
    detail = json.loads(run["detail_json"] or "{}")
    ctx = detail.get("context", {})
    nodes = [_node("question", "question", run["input_summary"] or "question")]
    edges = []
    for intent in detail.get("intents", []):
        nodes.append(_node(f"intent:{intent}", "intent", intent))
        edges.append({"source": "question", "target": f"intent:{intent}", "relation": "understood as"})
    for key, values in (detail.get("entities") or {}).items():
        for v in values if isinstance(values, list) else [values]:
            if key == "weeks":
                continue
            nid = f"entity:{key}:{v}"
            nodes.append(_node(nid, "entity", str(v), detail=key))
            edges.append({"source": "question", "target": nid, "relation": "mentions"})
    for t in store.tool_calls_for(run["id"]):
        nid = f"tool:{t['id']}"
        nodes.append(_node(nid, "tool", t["tool"], detail=f"{t['duration_ms']} ms · {t['status']}"))
        edges.append({"source": (f"intent:{detail['intents'][0]}" if detail.get("intents") else "question"),
                      "target": nid, "relation": "calls"})
    for i, s in enumerate(detail.get("sources", [])):
        nid = f"source:{s.get('id', i)}"
        nodes.append(_node(nid, "source", f"[{s.get('id')}] {s.get('label', '')}", detail=s.get("ref", "")))
        tools = [n["id"] for n in nodes if n["type"] == "tool"]
        edges.append({"source": tools[min(i, len(tools) - 1)] if tools else "question", "target": nid,
                      "relation": "returns"})
    return {"runs": choices, "run": {"id": run["id"], "question": run["input_summary"], "status": run["status"],
                                     "duration_ms": run["duration_ms"], "mode": detail.get("mode"),
                                     "started_at": run["started_at"]},
            "nodes": nodes, "edges": edges, "scope": ctx}


def procedure(username: str) -> dict:
    from app import quality

    o = quality.overview(username)
    t, review = o["totals"], o["review"]
    store = get_store()
    images = store.query("SELECT COUNT(*) AS n FROM inspection_items i JOIN inspection_batches b ON b.id = i.batch_id"
                         " WHERE b.username = ?", (username,))[0]["n"]
    pending = sum(1 for r in o["recommendations"] if r["grade"] == "Not Good" and not r["corrected"])
    runs = store.query("SELECT COUNT(*) AS n FROM agent_runs")[0]["n"]
    counts = {"inspect": images, "detect": t["potatoes"], "grade": t["graded"], "accept": t["Good"],
              "review": t["Moderate"], "reject": t["Not Good"], "approval": pending, "reimage": t["Not graded"],
              "correct": review["corrections"], "learn": runs}
    return {"nodes": [_node(i, k, label, count=counts[i]) for i, label, k in PROCEDURE_NODES],
            "edges": [{"source": a, "target": b, "relation": r} for a, b, r in PROCEDURE_EDGES]}


def activity(limit: int = 60) -> dict:
    store = get_store()
    runs = store.query("SELECT id, agent, status, started_at, duration_ms, input_summary FROM agent_runs"
                       " ORDER BY started_at DESC LIMIT ?", (limit,))
    stats = store.query("SELECT agent, COUNT(*) AS runs, AVG(duration_ms) AS avg_ms, MAX(duration_ms) AS max_ms,"
                        " SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors FROM agent_runs GROUP BY agent")
    tools = store.query("SELECT tool, COUNT(*) AS calls, AVG(duration_ms) AS avg_ms,"
                        " SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors FROM tool_calls GROUP BY tool"
                        " ORDER BY calls DESC LIMIT 15")
    for r in runs:
        r["tool_calls"] = store.tool_calls_for(r["id"])
    return {"runs": runs, "agents": stats, "tools": tools}
