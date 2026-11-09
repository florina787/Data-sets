"""Semantic Spine: Ontology → Knowledge Graph → Context Graph → Procedural Graph → Agent → Trace & Learn.

* Knowledge graph  (what is true)      — entity types and relationships counted from the cleaned ledger.
* Context graph    (what matters now)  — the small subgraph one question needs: its metric, filters, tables, the
                                          data-quality facts and policies that touch *those* rows. Built from a real run.
* Procedural graph (what to do next)   — the supervisor's routing as (step, condition, next step) triplets. Tests replay
                                          real runs and check each trace is a valid path through it.
* Trace & learn                        — recorded runs aggregated into improvement *proposals*. Nothing is applied
                                          automatically: a person adds a metric to the catalog, or doesn't.
"""
from __future__ import annotations

import re
from collections import Counter

from . import db
from .agent import memory
from .semantic.catalog import METRICS


def _q(sql, p=None):
    return db.connection().execute(sql, p or []).fetchall()


# ---------------------------------------------------------------- ontology + knowledge graph
def knowledge() -> dict:
    n = lambda sql: int(_q(sql)[0][0])  # noqa: E731
    entities = [
        {"id": "Account", "count": n("SELECT COUNT(*) FROM accounts"), "key": "account_id", "fact": "latest-invoice snapshot"},
        {"id": "Invoice", "count": n("SELECT COUNT(*) FROM invoices"), "key": "invoice_id", "fact": "one row per invoice after dedup"},
        {"id": "Plan", "count": n("SELECT COUNT(DISTINCT plan) FROM invoices"), "key": "plan", "fact": "Starter $49 · Pro $99 · Enterprise $299"},
        {"id": "Region", "count": n("SELECT COUNT(DISTINCT region) FROM invoices WHERE region IS NOT NULL"), "key": "region", "fact": "NA · EMEA · APAC · LATAM"},
        {"id": "Status", "count": n("SELECT COUNT(DISTINCT status) FROM invoices"), "key": "status", "fact": "paid · pending · failed · refunded · void"},
        {"id": "Currency", "count": n("SELECT COUNT(DISTINCT currency) FROM invoices"), "key": "currency", "fact": "USD · EUR · GBP (FX open decision)"},
        {"id": "Metric", "count": len(METRICS), "key": "metric id", "fact": "approved SQL definitions (semantic catalog)"},
        {"id": "Policy", "count": 2, "key": "PDR id", "fact": "PDR-001 FX · PDR-002 identity (open)"},
        {"id": "AuditRecord", "count": n("SELECT COUNT(*) FROM rejected_rows"), "key": "raw_row_number", "fact": "rows kept out of totals, with reason"},
        {"id": "Conflict", "count": n("SELECT COUNT(*) FROM dedup_conflicts"), "key": "invoice_id", "fact": "systems disagreed on status"},
    ]
    relations = [
        ("Account", "billed", "Invoice", n("SELECT COUNT(*) FROM invoices")),
        ("Invoice", "on_plan", "Plan", n("SELECT COUNT(*) FROM invoices")),
        ("Account", "in_region", "Region", n("SELECT COUNT(*) FROM accounts WHERE region IS NOT NULL")),
        ("Invoice", "has_status", "Status", n("SELECT COUNT(*) FROM invoices")),
        ("Invoice", "priced_in", "Currency", n("SELECT COUNT(*) FROM invoices")),
        ("Currency", "governed_by", "Policy", n("SELECT COUNT(*) FROM invoices WHERE currency <> 'USD'")),
        ("Account", "identity_question", "Policy", n("SELECT COUNT(*) FROM (SELECT account_id FROM invoices GROUP BY 1 HAVING COUNT(DISTINCT account_name) > 1)")),
        ("Invoice", "resolved_from", "Conflict", n("SELECT COUNT(*) FROM dedup_conflicts")),
        ("AuditRecord", "duplicate_of", "Invoice", n("SELECT COUNT(*) FROM rejected_rows")),
        ("Metric", "computed_from", "Invoice", sum(1 for m in METRICS.values() if m.grain == "invoice")),
        ("Metric", "computed_from", "Account", sum(1 for m in METRICS.values() if m.grain == "account")),
    ]
    return {"layer": "knowledge", "question": "What is true?", "entities": entities,
            "relations": [{"from": a, "rel": r, "to": b, "count": c} for a, r, b, c in relations]}


# ---------------------------------------------------------------- procedural graph (mirrors app/agent/supervisor.py::_dispatch)
PROCEDURE = [
    # (step, condition, next_step)
    ("question", "always", "guards"),
    ("guards", "write request", "refuse_write"),
    ("guards", "no evidence in data (why/forecast/live rates)", "decline_out_of_scope"),
    ("guards", "otherwise", "router"),
    ("router", "explain / definition", "explain"),
    ("router", "concept question about a catalog metric", "explain"),
    ("router", "concept question outside the catalog", "general_chat"),
    ("router", "cleaning / dedup / reconciliation question", "data_quality"),
    ("router", "follow-up patches previous plan", "semantic_planner"),
    ("router", "approved metric, confidence ≥ 0.6", "semantic_planner"),
    ("router", "greeting / no data words", "general_chat"),
    ("router", "data question, no confident plan, Qwen offline", "clarify"),
    ("router", "data question, no confident plan, Qwen online", "qwen_sql"),
    ("semantic_planner", "compile approved SQL", "sql_guard"),
    ("qwen_sql", "generated SQL", "sql_guard"),
    ("sql_guard", "rejected (once)", "qwen_sql"),
    ("sql_guard", "passes", "duckdb_read_only"),
    ("duckdb_read_only", "rows", "caveats"),
    ("duckdb_read_only", "rows (Qwen path)", "grounding_check"),
    ("grounding_check", "numbers grounded or replaced by table", "answer"),
    ("caveats", "attach data-quality facts in scope", "answer"),
    ("data_quality", "audit tables", "answer"),
    ("explain", "definitions + SQL", "answer"),
    ("general_chat", "labelled not-from-data", "answer"),
    ("answer", "recorded", "trace"),
    ("refuse_write", "recorded", "trace"), ("decline_out_of_scope", "recorded", "trace"), ("clarify", "recorded", "trace"),
    ("policy_change", "requires", "finance_owner_approval"),
    ("finance_owner_approval", "approved, then explicit apply", "rebuild"),
]
STEP_LABEL = {"question": "Question", "guards": "Guards", "router": "Router", "semantic_planner": "Semantic planner", "qwen_sql": "Qwen text-to-SQL",
              "sql_guard": "SQL guard", "duckdb_read_only": "DuckDB (read-only)", "caveats": "Scope caveats", "grounding_check": "Grounding check",
              "data_quality": "Data-quality tool", "explain": "Explain", "general_chat": "General chat", "clarify": "Ask to clarify",
              "refuse_write": "Refuse write", "decline_out_of_scope": "Decline (no evidence)", "answer": "Answer", "trace": "Trace",
              "policy_change": "Policy change", "finance_owner_approval": "Finance-owner approval", "rebuild": "Rebuild"}


def procedure() -> dict:
    return {"layer": "procedural", "question": "What do I do next?", "steps": STEP_LABEL,
            "triplets": [{"from": a, "when": c, "to": b} for a, c, b in PROCEDURE],
            "note": "Mirrors app/agent/supervisor.py. Guides the next step; the policy-change branch is human-only."}


def path_from_trace(resp: dict) -> list[str]:
    """Map a real /ask response to the sequence of procedural steps it actually took."""
    path = ["question", "guards"]
    route = " ".join(t.get("detail", "") for t in resp["trace"] if t.get("step") == "route").lower()
    tools = [t.get("tool") for t in resp["trace"] if t.get("tool")]
    intent = resp["intent"]
    if intent == "out_of_scope":
        return path + (["refuse_write"] if "write" in route else ["decline_out_of_scope"]) + ["trace"]
    path.append("router")
    if intent == "explain":
        path.append("explain")
    elif intent == "general":
        path.append("general_chat")
    elif intent == "data_quality":
        path.append("data_quality")
    elif intent == "clarify":
        return path + ["clarify", "trace"]
    elif "run_llm_sql" in tools:
        path += ["qwen_sql", "sql_guard", "duckdb_read_only", "grounding_check"]
    elif "run_metric_query" in tools:
        path += ["semantic_planner", "sql_guard", "duckdb_read_only", "caveats"]
    return path + ["answer", "trace"]


def is_valid_path(path: list[str]) -> bool:
    edges = {(a, b) for a, _, b in PROCEDURE}
    return all((a, b) in edges for a, b in zip(path, path[1:]))


# ---------------------------------------------------------------- context graph for one question
def context(question: str, session_id: str | None = None) -> dict:
    from .agent import supervisor
    resp = supervisor.ask(question, session_id)
    nodes, edges = [{"id": "q", "type": "question", "label": question[:80]}], []

    def add(i, t, label, detail="", parent="q", rel=""):
        nodes.append({"id": i, "type": t, "label": label, "detail": detail}); edges.append({"from": parent, "to": i, "rel": rel})

    add("intent", "intent", resp["intent"], f"planner: {resp['planner']}", rel="routed_as")
    for d in resp.get("metric_definitions") or []:
        add(f"m:{d['id']}", "metric", d["label"], d["definition"], "intent", "uses_metric")
    for k, v in (resp.get("filters") or {}).items():
        add(f"f:{k}", "filter", f"{k} = {v}", "", "intent", "filtered_by")
    for t in resp.get("sources") or []:
        add(f"t:{t}", "table", t, "", "intent", "reads")
    for i, c in enumerate(resp.get("caveats") or []):
        kind = ("Conflict" if "conflicting duplicate" in c else "Ambiguous dates" if "ambiguous" in c else "FX policy" if c.startswith("FX") else
                "Snapshot rule" if "latest invoice" in c else "Future-dated" if "after today" in c else "Caveat")
        add(f"c:{i}", "fact", kind, c, "intent", "in_scope")
    uses_amount = any(re.search(r"amount_usd", d.get("sql", "")) for d in resp.get("metric_definitions") or []) or "amount_usd" in (resp.get("sql") or "")
    if uses_amount:
        add("p:PDR-001", "policy", "PDR-001 FX direction", "open decision — active rule v1.0 (documented)", "intent", "depends_on")
    if "accounts" in (resp.get("sources") or []) or "account" in (resp.get("sql") or ""):
        add("p:PDR-002", "policy", "PDR-002 account identity", "open decision — account_id is the key", "intent", "depends_on")
    if resp.get("result"):
        add("ans", "answer", f"{resp['result']['row_count']} row(s)", (resp.get("answer") or "")[:200], "intent", "produced")
    path = path_from_trace(resp)
    return {"layer": "context", "question": "What matters now?", "nodes": nodes, "edges": edges,
            "procedural_path": path, "path_valid": is_valid_path(path), "answer": resp.get("answer"), "sql": resp.get("sql"),
            "run_id": resp["run_id"], "session_id": resp["session_id"]}


# ---------------------------------------------------------------- trace & learn
_MEASURE = re.compile(r"support tickets?|tickets|tenure|signup|cohort|median|percentile|retention|seats per|lifetime", re.I)


def learn(limit: int = 500) -> dict:
    runs = memory.recent_runs(limit)
    paths = Counter()
    outcomes = Counter()
    for r in runs:
        outcomes[(r["intent"], r["planner"], r["status"])] += 1
        paths[r["planner"] if r["status"] == "ok" else f"error:{r['status']}"] += 1
    misses = [r for r in runs if r["planner"] == "llm_sql" or r["intent"] == "clarify"]
    terms = Counter(m.group(0).lower() for r in misses for m in [_MEASURE.search(r["question"])] if m)
    proposals = [{"type": "add_metric_to_catalog", "term": t, "evidence_runs": c,
                  "why": f"'{t}' appeared in {c} question(s) that the approved catalog could not answer (sent to Qwen or asked to clarify).",
                  "status": "proposed — needs a person to define the metric in specs/financial_metrics.md first"} for t, c in terms.most_common(5)]
    errors = [r for r in runs if r["status"] != "ok"]
    if errors:
        proposals.append({"type": "review_failures", "term": ", ".join(sorted({e['status'] for e in errors}))[:80], "evidence_runs": len(errors),
                          "why": "Failed runs recorded in the trace store.", "status": "proposed — review in the Agent Control Tower"})
    return {"layer": "trace", "runs_analyzed": len(runs), "by_planner": dict(paths),
            "outcomes": [{"intent": i, "planner": p, "status": s, "runs": c} for (i, p, s), c in outcomes.most_common(12)],
            "proposals": proposals,
            "note": "Learning here means proposals from recorded traces. Nothing changes the catalog, policy or data automatically."}
