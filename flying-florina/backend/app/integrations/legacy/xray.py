"""Legacy X-Ray: landscape graph, risks and evidence-backed modernization options."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from app.core import db
from app.core.config import FIXTURES_DIR
from app.core.util import new_id, now_iso, sha256_text
from app.integrations.legacy.parsers import parse_upload

BUNDLED = [
    "legacy/mro_core_legacy.sql", "legacy/quality_system.sql", "legacy/inventory_flatfile.sql", "legacy/nightly_inventory.csv",
    "legacy/erp_sim_metadata.xml", "legacy/inventory_event.schema.json", "legacy/dependency_graph.json",
    "openapi/java_erp_service.yaml", "openapi/erp_simulator_projections.json", "openapi/supplier_portal.json",
]

SYSTEM_HINTS = {
    "MRO_CORE": "APP-03", "MRO Legacy Database": "APP-03", "Manufacturing Quality": "APP-09", "Flat-file Inventory": "APP-06",
    "Java ERP": "APP-04", "ERP Simulator": "APP-01", "Supplier Portal": "APP-10", "nightly_inventory": "APP-06",
    "erp_sim_metadata": "APP-01", "inventory_event": "APP-11",
}

CONTEXTS = {
    "Fleet & Telemetry": ["AIRCRAFT", "SENSOR"],
    "Maintenance Execution": ["WORK_ORDER", "WO_PART", "TECH"],
    "Inventory & Parts": ["PART", "STOCK", "INVENTORY", "REJECT"],
    "Quality": ["NCR", "CAPA", "CERT"],
}


def bundled_fixture_paths() -> list[str]:
    return list(BUNDLED)


def parse_bundled(names: list[str] | None = None) -> list[dict[str, Any]]:
    out = []
    for rel in names or BUNDLED:
        path = FIXTURES_DIR / rel
        raw = path.read_bytes()
        res = parse_upload(path.name, raw, 5 * 1024 * 1024)
        res["source"] = f"fixtures/{rel}"
        res["sha256"] = sha256_text(raw.decode("utf-8", "replace"))
        out.append(res)
    return out


def store_import(actor_id: str, filename: str, size: int, sha: str, result: dict[str, Any]) -> str:
    iid = new_id("IMP")
    with db.session(write=True) as conn:
        conn.execute("INSERT INTO legacy_imports VALUES (?,?,?,?,?,?,?,?)",
                     (iid, now_iso(), actor_id, filename, result.get("kind"), size, sha, db.jdump(result)))
    return iid


def user_imports() -> list[dict[str, Any]]:
    out = []
    for r in db.query("SELECT * FROM legacy_imports ORDER BY ts"):
        res = db.jload(r["result_json"], {})
        res["source"] = f"upload:{r['id']}:{r['filename']}"
        res["import_id"] = r["id"]
        res["sha256"] = r["sha256"]
        out.append(res)
    return out


def _system_for(res: dict[str, Any]) -> str | None:
    text = " ".join(str(x) for x in [res.get("metadata", {}).get("system", ""), res.get("title", ""), res.get("source", ""), res.get("filename", "")])
    for hint, app in SYSTEM_HINTS.items():
        if hint.lower() in text.lower():
            return app
    return None


def landscape(include_uploads: bool = True, include_bundled: bool = True) -> dict[str, Any]:
    parsed = (parse_bundled() if include_bundled else []) + (user_imports() if include_uploads else [])
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    unknowns: list[dict[str, Any]] = []

    graph = next((p for p in parsed if p["kind"] == "dependency_graph"), None)
    apps = graph["applications"] if graph else []
    for a in apps:
        nodes[a["id"]] = {"id": a["id"], "label": a["name"], "type": "system", "kind": a["kind"], "technology": a["technology"],
                          "criticality": a["criticality"], "owner": a["owner"], "auth": a["auth_method"], "batch_window": a.get("batch_window"),
                          "confidence": 0.9, "evidence": [graph["source"]], "last_doc_update": a["last_doc_update"]}
    for e in (graph["dependencies"] if graph else []):
        edges.append({"id": f"{e['source']}->{e['target']}", "source": e["source"], "target": e["target"], "label": f"{e['protocol']} ({e['frequency']})",
                      "kind": e["kind"], "confidence": 0.9, "evidence": graph["source"]})

    for p in parsed:
        findings += [{**f, "source": p["source"]} for f in p.get("findings", [])]
        sys_id = _system_for(p)
        if p["kind"] == "sql_ddl":
            for t in p["tables"]:
                nid = f"T:{t['name']}"
                nodes[nid] = {"id": nid, "label": t["name"], "type": "table", "parent": sys_id, "columns": len(t["columns"]),
                              "primary_key": t["primary_key"], "confidence": 1.0, "evidence": [p["source"]], "context": _context(t["name"])}
                if sys_id:
                    edges.append({"id": f"{sys_id}->{nid}", "source": sys_id, "target": nid, "label": "owns", "kind": "contains", "confidence": 1.0, "evidence": p["source"]})
            for v in p["views"]:
                nid = f"V:{v['name']}"
                nodes[nid] = {"id": nid, "label": v["name"], "type": "view", "parent": sys_id, "confidence": 1.0, "evidence": [p["source"]],
                              "context": _context(v["name"]), "read_only_candidate": True}
                for ref in v["references"]:
                    edges.append({"id": f"{nid}->T:{ref}", "source": nid, "target": f"T:{ref}", "label": "reads", "kind": "view", "confidence": 1.0, "evidence": p["source"]})
            for fk in p["foreign_keys"]:
                edges.append({"id": f"FK:{fk['from_table']}.{fk['from_column']}", "source": f"T:{fk['from_table']}", "target": f"T:{fk['to_table']}",
                              "label": f"FK {fk['from_column']}", "kind": "foreign_key", "confidence": 1.0, "evidence": p["source"]})
        elif p["kind"] == "openapi":
            nid = f"API:{p['title']}"
            nodes[nid] = {"id": nid, "label": f"{p['title']} v{p['version']}", "type": "api", "parent": sys_id, "operations": p["summary"]["operations"],
                          "write_operations": p["summary"]["write_operations"], "auth": [a["type"] for a in p["auth"]], "confidence": 1.0, "evidence": [p["source"]]}
            if sys_id:
                edges.append({"id": f"{sys_id}->{nid}", "source": sys_id, "target": nid, "label": "exposes", "kind": "contains", "confidence": 1.0, "evidence": p["source"]})
        elif p["kind"] == "csv":
            nid = f"FILE:{p['filename']}"
            nodes[nid] = {"id": nid, "label": p["filename"], "type": "file", "parent": sys_id or "APP-06", "rows": p["row_count"], "confidence": 1.0, "evidence": [p["source"]]}
            edges.append({"id": f"{sys_id or 'APP-06'}->{nid}", "source": sys_id or "APP-06", "target": nid, "label": "nightly export", "kind": "contains", "confidence": 1.0, "evidence": p["source"]})
        elif p["kind"] == "event_schema":
            nid = f"EVT:{p['topic']}"
            nodes[nid] = {"id": nid, "label": p["topic"], "type": "event", "parent": p.get("producer"), "confidence": 1.0, "evidence": [p["source"]]}
            if p.get("producer"):
                edges.append({"id": f"{p['producer']}->{nid}", "source": p["producer"], "target": nid, "label": "publishes", "kind": "event", "confidence": 0.8, "evidence": p["source"]})
        elif p["kind"] == "odata_metadata":
            for ent in p["entities"]:
                nid = f"ODATA:{ent['name']}"
                nodes[nid] = {"id": nid, "label": f"{ent['name']} (OData-like)", "type": "entity", "parent": sys_id or "APP-01", "confidence": 1.0, "evidence": [p["source"]]}
                edges.append({"id": f"{sys_id or 'APP-01'}->{nid}", "source": sys_id or "APP-01", "target": nid, "label": "projection", "kind": "contains", "confidence": 1.0, "evidence": p["source"]})

    # Unknowns are explicit nodes, never assumptions.
    unknowns = [
        {"id": "U1", "question": "Which consumers read TMP_SYNC_2011 and MRO_SENSOR_RAW?", "why": "No FK or documented consumer; opaque CH_xx columns."},
        {"id": "U2", "question": "Is change data capture permitted on MRO_CORE by the DBA team and vendor support terms?", "why": "Required before any CDC pattern."},
        {"id": "U3", "question": "Which customer ERP/IFS Cloud version and which documented projections are licensed and reachable?", "why": "Never assume undocumented endpoints or access."},
        {"id": "U4", "question": "Is the nightly CSV the physical-count system of record for inventory?", "why": "ERP and CSV disagree for P-7731 (INC-003)."},
        {"id": "U5", "question": "Who owns the Java ERP /admin/sql endpoint and can it be disabled?", "why": "Arbitrary SQL endpoint found in OpenAPI fixture."},
    ]
    for u in unknowns:
        nodes[f"UNK:{u['id']}"] = {"id": f"UNK:{u['id']}", "label": u["question"], "type": "unknown", "confidence": 0.0, "evidence": [], "why": u["why"]}

    degree = Counter()
    for e in edges:
        if nodes.get(e["source"], {}).get("type") == "system" and nodes.get(e["target"], {}).get("type") == "system":
            degree[e["source"]] += 1
            degree[e["target"]] += 1
    hotspots = [{"system": s, "name": nodes[s]["label"], "integration_degree": d} for s, d in degree.most_common(4)]
    contexts: dict[str, list[str]] = defaultdict(list)
    for n in nodes.values():
        if n.get("context"):
            contexts[n["context"]].append(n["label"])
    stale_docs = [{"system": n["id"], "name": n["label"], "last_doc_update": n["last_doc_update"]}
                  for n in nodes.values() if n["type"] == "system" and n.get("last_doc_update", "9999") < "2024-01-01"]
    batch = [{"system": n["id"], "name": n["label"], "window": n["batch_window"]} for n in nodes.values() if n["type"] == "system" and n.get("batch_window")]
    sev = Counter(f["severity"] for f in findings)
    return {
        "sources": [{"source": p["source"], "kind": p["kind"], "sha256": p.get("sha256"), "summary": p.get("summary", {})} for p in parsed],
        "nodes": list(nodes.values()), "edges": edges, "findings": findings, "unknowns": unknowns,
        "hotspots": hotspots, "bounded_contexts": [{"name": k, "objects": sorted(v)} for k, v in sorted(contexts.items())],
        "stale_docs": stale_docs, "batch_windows": batch,
        "summary": {"systems": sum(1 for n in nodes.values() if n["type"] == "system"),
                    "tables": sum(1 for n in nodes.values() if n["type"] == "table"),
                    "apis": sum(1 for n in nodes.values() if n["type"] == "api"),
                    "findings": len(findings), "high": sev.get("high", 0), "medium": sev.get("medium", 0), "unknowns": len(unknowns)},
        "parsed": parsed,
    }


def _context(name: str) -> str | None:
    for ctx, keys in CONTEXTS.items():
        if any(k in name for k in keys):
            return ctx
    return None


def recommendations(ls: dict[str, Any]) -> list[dict[str, Any]]:
    kinds = Counter(f["kind"] for f in ls["findings"])
    has_view = any(n["type"] == "view" for n in ls["nodes"])
    no_pk = kinds.get("no_primary_key", 0)
    ev = lambda *k: [f"{f['source']}: {f['kind']} {f['object']}" for f in ls["findings"] if f["kind"] in k][:4]  # noqa: E731

    def rec(rid, pattern, title, why, prereq, evidence, cls, deps, risk, steps, rollback, tests, effort, tradeoffs, conf, decisions, diagram, applies=True):
        return {"id": rid, "pattern": pattern, "title": title, "why": why, "prerequisites": prereq, "evidence": evidence,
                "security_classification": cls, "dependencies": deps, "migration_risk": risk, "implementation_steps": steps,
                "rollback": rollback, "test_plan": tests, "effort_assumption": effort, "tradeoffs": tradeoffs, "confidence": conf,
                "human_decisions": decisions, "diagram": diagram, "applies": applies}

    return [
        rec("R1", "read_only_view", "Read-only parts availability view behind a typed adapter",
            "V_PART_AVAILABILITY already joins part master and stock; exposing it read-only gives agents verified inventory without touching transactions.",
            ["DBA creates a read-only account limited to the view", "Parameterized queries only", "No model-generated SQL against production"],
            [f"View V_PART_AVAILABILITY found ({'yes' if has_view else 'no'})"] + ev("stale_counts", "multi_value_column"),
            "INTERNAL (inventory); RESTRICTED for work-order joins", ["APP-03"], "low",
            ["Create read-only DB role", "Generate FastAPI adapter + Pydantic models", "Wrap as MCP tool get_part_availability", "Contract + security tests", "Gateway registration"],
            "Drop the read-only role and remove the gateway route; no data was changed.",
            ["Contract tests against fixture backend", "Negative tests: SQL meta-characters, unknown part, missing scope", "Load test p95 < 300 ms (target)"],
            "1-2 engineer-weeks (assumption)", "Fast and safe; still tied to legacy schema semantics until an ACL is added.", 0.85,
            ["Confirm DBA approval for read-only role", "Confirm the CSV vs ERP system of record (U4)"],
            {"nodes": ["Agent", "MCP tool", "Typed adapter", "Read-only view", "MRO_CORE"], "edges": [[0, 1], [1, 2], [2, 3], [3, 4]]}, has_view),
        rec("R2", "api_facade_strangler", "Strangler fig: API facade in front of the Java ERP service",
            "The Java service mixes reads, writes and an /admin/sql endpoint. A facade lets consumers move to a governed contract while legacy stays in place.",
            ["API gateway route ownership", "Inventory of current consumers", "Disable or firewall /admin/sql"],
            ev("dangerous_endpoint", "static_api_key", "no_pagination"), "INTERNAL", ["APP-04", "APP-12"], "medium",
            ["Front read operations with the gateway", "Add pagination and response caps", "Migrate consumers one at a time", "Retire direct calls"],
            "Route traffic back to the original endpoints at the gateway.", ["Consumer-driven contract tests", "Shadow traffic comparison"],
            "4-8 engineer-weeks (assumption)", "Gradual and reversible; temporarily two paths to maintain.", 0.75,
            ["Which consumers move first", "Deprecation timeline for /admin/sql"],
            {"nodes": ["Consumers", "API gateway", "Facade", "Java ERP service"], "edges": [[0, 1], [1, 2], [2, 3]]}),
        rec("R3", "anti_corruption_layer", "Anti-corruption layer with canonical Part, Stock and WorkOrder models",
            "Legacy names (PART_NO, QTY_OH, STATUS_CD, CH_01) leak semantics; an ACL translates them once into canonical models used by every new consumer.",
            ["Canonical model agreed with SMEs", "Mapping of opaque columns (U1)"], ev("opaque_columns", "multi_value_column"), "INTERNAL", ["APP-01", "APP-03"], "medium",
            ["Define canonical schemas", "Implement translators in adapters", "Version the contract", "Document unmapped fields"],
            "Consumers can pin the previous contract version.", ["Golden-file mapping tests", "Round-trip tests"], "2-4 engineer-weeks (assumption)",
            "Extra mapping code to maintain; prevents legacy coupling from spreading.", 0.7, ["Owner of canonical model"],
            {"nodes": ["Legacy schema", "ACL translators", "Canonical API"], "edges": [[0, 1], [1, 2]]}),
        rec("R4", "batch_bridge", "Validated batch bridge for the nightly inventory CSV",
            "The CSV has invalid record types, empty quantities and stale counts. Validate, quarantine, reconcile and audit instead of loading blindly.",
            ["Quarantine location", "Reconciliation owner"], ev("invalid_record_type", "missing_values", "stale_counts"), "INTERNAL", ["APP-05", "APP-06", "APP-01"], "low",
            ["Schema-validate each row", "Quarantine rejects with reasons", "Reconcile against ERP counts", "Emit audit record per batch", "Idempotent re-run"],
            "Disable the bridge; legacy batch continues unchanged.", ["Fixture with bad rows", "Replay same file twice (idempotency)"],
            "1-2 engineer-weeks (assumption)", "Keeps batch latency (nightly) but makes it trustworthy.", 0.8, ["Reconciliation rules for conflicts"],
            {"nodes": ["CSV export", "Validator", "Quarantine", "Reconciler", "ERP-SIM"], "edges": [[0, 1], [1, 2], [1, 3], [3, 4]]}),
        rec("R5", "cdc_event_stream", "Change data capture to an event stream (conditional)",
            "Near-real-time inventory events would remove the nightly gap, but only if CDC is permitted and tables have stable keys.",
            ["DBA and vendor approval (U2)", "Primary keys on captured tables", "Event schema registry"],
            ev("no_primary_key") + ["Event schema inventory.count.changed.v1 found"], "INTERNAL", ["APP-03", "APP-11"], "high" if no_pk else "medium",
            ["Confirm permission", "Add keys where missing", "Capture MRO_STOCK_LOC only", "Publish canonical events", "Consumers handle replay and ordering"],
            "Stop the connector; consumers fall back to the batch bridge.", ["Ordering and replay tests", "Consistency checks vs nightly counts"],
            "4-6 engineer-weeks (assumption)", "Fresher data; more operational complexity and consistency questions.", 0.45,
            ["Is CDC allowed at all?", "Which tables first"], {"nodes": ["MRO_CORE", "CDC connector", "Event bus", "Consumers"], "edges": [[0, 1], [1, 2], [2, 3]]}, applies=False),
        rec("R6", "rag_documents", "Version-aware, access-filtered retrieval over technical documents",
            "Document repository has superseded and unprovenanced revisions; retrieval must filter by classification first and cite revision and provenance.",
            ["Document metadata export with revisions and classifications"], ["DOC-007 superseded", "DOC-012 missing provenance", "DOC-021 prompt-injection text"],
            "Mixed: PUBLIC to RESTRICTED", ["APP-07"], "low",
            ["Index metadata + text locally", "Filter by label/role before ranking", "Quarantine instruction-like text", "Cite id, revision, date"],
            "Disable retrieval tool; users search the repository directly.", ["Unauthorized document never returned", "Superseded doc never authoritative"],
            "1-3 engineer-weeks (assumption)", "Improves answers; requires disciplined document metadata.", 0.8, ["Document owners confirm classifications"],
            {"nodes": ["Doc repository", "Indexer", "Access filter", "Ranker", "Citations"], "edges": [[0, 1], [1, 2], [2, 3], [3, 4]]}),
        rec("R7", "supported_erp_apis", "Use documented ERP/IFS Cloud REST/OData projections where licensed",
            "Prefer vendor-documented, supported projections over database access. This demo has no IFS connection; projection names in the fixture are fictional.",
            ["Customer confirms version, licensing and documented projections (U3)", "OAuth2 client with least-privilege scopes"],
            ["erp_simulator_projections.json declares OAuth2 client credentials with scope inventory.read (fictional)"], "INTERNAL", ["APP-01"], "medium",
            ["Confirm documented projections", "Request read scopes only", "Generate typed client", "Paginate with $top/$skip"],
            "Remove client registration.", ["Contract tests against vendor sandbox (customer-provided)"], "2-3 engineer-weeks (assumption)",
            "Supported and upgrade-safe; depends on customer access and vendor documentation.", 0.5, ["Which ERP environment and scopes are approved"],
            {"nodes": ["Adapter", "OAuth2 IdP", "ERP projection"], "edges": [[0, 1], [0, 2]]}),
        rec("R8", "mcp_facade", "MCP facade over the secured adapter (agent interface only)",
            "Expose narrow, read-only, version-pinned tools to agents. MCP is not the security boundary: the gateway and adapter enforce identity, scope and policy.",
            ["R1 adapter in place", "Tool allowlist and schema pinning", "Per-invocation authorization"], ["DOC-025 MCP onboarding standard"],
            "INTERNAL", ["R1"], "low", ["Wrap adapter function as MCP tool", "Pin name/version/schema hash", "Log redacted invocations", "Deny untrusted tools"],
            "Unregister tool; adapter remains for non-agent consumers.", ["Untrusted tool registration rejected", "Tool call without scope denied"],
            "0.5-1 engineer-week (assumption)", "Simple for agents; must not bypass API governance.", 0.85, ["Which tools are exposed"],
            {"nodes": ["Agent", "MCP server", "Policy gateway", "Adapter"], "edges": [[0, 1], [1, 2], [2, 3]]}),
    ]


def roadmap() -> list[dict[str, Any]]:
    return [
        {"phase": "Days 0-30: Discover & secure", "owner": "Enterprise Architect + Security Officer",
         "items": ["Confirm unknowns U1-U5 with system owners", "Read-only DB role for V_PART_AVAILABILITY (R1)", "Firewall /admin/sql (R2 prerequisite)",
                   "Classify documents; fix DOC-012 provenance (R6)"], "dependencies": ["DBA approval", "Security review"], "exit": "Read-only adapter passing contract tests in a non-production environment"},
        {"phase": "Days 31-60: Bridge & pilot", "owner": "Forward Deployed Engineer + Maintenance Planner",
         "items": ["MCP tool over adapter (R8)", "Validated CSV batch bridge (R4)", "Pilot AC-204-style investigation workflow with human approval gate"],
         "dependencies": ["Phase 1 exit", "Pilot users named"], "exit": "Pilot users complete workflows; zero policy bypasses in audit"},
        {"phase": "Days 61-90: Facade & decide", "owner": "Enterprise Architect + Executive sponsor",
         "items": ["API facade for read operations (R2)", "Canonical models / ACL (R3)", "Decide on CDC (R5) and documented ERP projections (R7)", "Executive readout with measured pilot data"],
         "dependencies": ["Pilot metrics", "Vendor documentation"], "exit": "Go/no-go decision based on measured, not modeled, results"},
    ]
