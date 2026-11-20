"""Shield research workflow end to end, through the API, with real tools and real range isolation."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from florome.config import Settings
from florome.main import create_app
from tests.conftest import H

EXPECTED = {
    ("search_invoices", "sql_injection"): "confirmed", ("by_customer", "sql_injection"): "disproven",
    ("get_invoice", "broken_access_control"): "confirmed", ("get_my_invoice", "broken_access_control"): "disproven",
    ("download", "path_traversal"): "confirmed", ("read_file", "path_traversal"): "disproven",
    ("ping", "command_injection"): "confirmed", ("echo", "command_injection"): "disproven",
    ("import_ledger", "unsafe_deserialization"): "confirmed",
}


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    s = Settings(database_url=f"sqlite:///{tmp_path_factory.mktemp('shield') / 'db.sqlite'}")
    app = create_app(s)
    with TestClient(app) as c:
        target = next(t for t in c.get("/api/v1/shield/repositories", headers=H("admin")).json()["authorized_targets"] if t["name"] == "ledgerlite")
        repo = c.post("/api/v1/shield/repositories", json={"name": "ledgerlite", "path": target["path"]}, headers=H("admin")).json()
        c.post(f"/api/v1/shield/repositories/{repo['id']}/ingest", headers=H("operator"))
        scan = c.post(f"/api/v1/shield/repositories/{repo['id']}/scan", headers=H("operator")).json()
        hyps = c.get(f"/api/v1/shield/hypotheses?repository_id={repo['id']}", headers=H("viewer")).json()
        for h in hyps:
            c.post(f"/api/v1/shield/hypotheses/{h['id']}/verify", headers=H("admin"))
        hyps = c.get(f"/api/v1/shield/hypotheses?repository_id={repo['id']}", headers=H("viewer")).json()
        yield {"c": c, "repo": repo, "scan": scan, "hyps": hyps, "target": target}


def test_scan_runs_real_tools(env):
    tools = {t["tool"]: t for t in env["scan"]["tools"]}
    assert tools["opengrep"]["status"] == "succeeded" and tools["opengrep"]["version"].startswith("1.")
    assert tools["bandit"]["status"] == "succeeded" and tools["trivy"]["status"] == "succeeded"
    assert env["scan"]["status"] == "succeeded"


def test_graph_has_source_derived_relationships_with_provenance(env):
    g = env["c"].get(f"/api/v1/shield/repositories/{env['repo']['id']}/graph", headers=H("viewer")).json()
    routes = {n["name"]: n for n in g["nodes"] if n["kind"] == "route"}
    assert routes["download"]["trust_boundary"] == "unauthenticated_input" and routes["get_invoice"]["trust_boundary"] == "authenticated_input"
    src = (Path(env["target"]["path"]) / "app.py").read_text().splitlines()
    for n in routes.values():  # every route node points at the line that defines it
        assert n["name"] in src[n["line"] - 1]
    flows = [e for e in g["edges"] if e["kind"] == "data_flow"]
    assert flows and all(e["provenance"]["resolution"] == "intraprocedural, name-based" for e in flows)
    assert g["snapshot"]["commit"] and len(g["snapshot"]["tree_hash"]) == 64
    auth = [e for e in g["edges"] if e["kind"] == "authenticated_by"]
    assert {e["source"] for e in auth} >= {routes["get_invoice"]["id"], routes["search_invoices"]["id"]}


def test_every_labelled_site_is_adjudicated_correctly(env):
    got = {(h["function"], h["vuln_class"]): h["status"] for h in env["hyps"]}
    for key, want in EXPECTED.items():
        assert got[key] == want, (key, got.get(key))


def test_false_positives_rejected_by_execution_not_assertion(env):
    decoy = next(h for h in env["hyps"] if h["function"] == "echo")
    d = env["c"].get(f"/api/v1/shield/hypotheses/{decoy['id']}", headers=H("viewer")).json()
    assert d["status"] == "disproven" and "argument_list_without_shell" in d["status_basis"]
    runs = [r for r in d["verification_runs"] if r["purpose"] == "verify"]
    assert len(runs) == 2 and all(r["outcome"] == "not_reproduced" for r in runs)


def test_confirmed_finding_has_reproducible_isolated_evidence(env):
    h = next(x for x in env["hyps"] if x["function"] == "ping")
    d = env["c"].get(f"/api/v1/shield/hypotheses/{h['id']}", headers=H("viewer")).json()
    runs = [r for r in d["verification_runs"] if r["purpose"] == "verify"]
    assert [r["outcome"] for r in runs] == ["reproduced", "reproduced"]
    assert all(r["isolation"]["network_namespace"] is True and r["isolation"]["python_isolated_mode"] for r in runs)
    assert d["severity"] == "critical" and "without authentication" in d["severity_basis"]
    assert d["source"]["lines"][d["line"] - d["source"]["start_line"]].strip().startswith("return subprocess.run")
    assert d["model_provenance"] is None  # deterministic engine: no model was involved


def test_duplicate_tool_findings_merge_into_one_hypothesis(env):
    h = next(x for x in env["hyps"] if x["function"] == "search_invoices" and x["vuln_class"] == "sql_injection")
    tools = [s for s in h["supporting"] if s["type"] == "tool"]
    assert {t["detail"].split()[0] for t in tools} == {"opengrep", "bandit"}
    assert sum(1 for x in env["hyps"] if x["function"] == "search_invoices" and x["vuln_class"] == "sql_injection") == 1


def test_unattributed_tool_evidence_is_kept_but_inconclusive(env):
    mod = [h for h in env["hyps"] if h["function"].startswith("<module")]
    assert mod and all(h["status"] == "inconclusive" for h in mod)


def test_confirmed_high_findings_enter_florome_incidents(env):
    c = env["c"]
    incs = c.get("/api/v1/incidents", headers=H("viewer")).json()["items"]
    shield_incs = [i for i in incs if i["title"].startswith("Security:")]
    assert len(shield_incs) == 5
    assert any("command injection in ping" in i["title"] for i in shield_incs)


def test_patch_generation_regression_and_independent_review(env):
    c = env["c"]
    h = next(x for x in env["hyps"] if x["function"] == "download")
    d = c.post(f"/api/v1/shield/hypotheses/{h['id']}/patch", headers=H("operator")).json()
    patch = d["patches"][-1]
    assert patch["status"] == "verified" and patch["regression"]["exploit_blocked_runs"] == 2 and patch["regression"]["functional_ok"]
    assert "+    if not str(_target).startswith" in patch["diff"]
    body = {"decision": "approve", "patch_hash": patch["patch_hash"]}
    assert c.post(f"/api/v1/shield/patches/{patch['id']}/review", json=body, headers=H("viewer")).status_code == 403  # no shield:review
    r = c.post(f"/api/v1/shield/patches/{patch['id']}/review", json={**body, "patch_hash": "0" * 64}, headers=H("approver"))
    assert r.status_code == 409
    assert c.post(f"/api/v1/shield/patches/{patch['id']}/review", json=body, headers=H("approver")).json()["status"] == "approved_for_review"
    # the repository itself is never modified
    assert "os.path.join(FILES, name)" in (Path(env["target"]["path"]) / "app.py").read_text()


def test_requester_cannot_review_own_patch(env):
    c = env["c"]
    h = next(x for x in env["hyps"] if x["function"] == "ping")
    patch = c.post(f"/api/v1/shield/hypotheses/{h['id']}/patch", headers=H("admin")).json()["patches"][-1]
    r = c.post(f"/api/v1/shield/patches/{patch['id']}/review", json={"decision": "approve", "patch_hash": patch["patch_hash"]}, headers=H("admin"))
    assert r.status_code == 403 and "Separation of duties" in r.json()["detail"]


def test_patch_refused_for_unconfirmed_finding(env):
    h = next(x for x in env["hyps"] if x["function"] == "echo")
    assert env["c"].post(f"/api/v1/shield/hypotheses/{h['id']}/patch", headers=H("operator")).status_code == 409


def test_incremental_reingest_reuses_unchanged_files(env):
    out = env["c"].post(f"/api/v1/shield/repositories/{env['repo']['id']}/ingest", headers=H("operator")).json()
    st = out["latest_snapshot"]["stats"]
    assert st["parsed"] == 0 and st["reused"] == st["files"] and st["symbols"] > 0


def test_agent_executions_are_recorded(env):
    a = env["c"].get("/api/v1/shield/agents", headers=H("viewer")).json()
    names = {e["agent"] for e in a["executions"]}
    assert {"repository_intelligence", "static_analysis", "dependency_security", "security_hypothesis", "independent_verification",
            "evidence_adjudicator", "patch_engineering", "incident_investigation"} <= names
    assert set(a["registry"]["independent_verification"]["tools"]) == {"cyber_range"}


def test_cross_tenant_isolation(env):
    c = env["c"]
    h = env["hyps"][0]
    assert c.get(f"/api/v1/shield/hypotheses/{h['id']}", headers=H("admin", "halcyon")).status_code == 404
    assert c.post(f"/api/v1/shield/hypotheses/{h['id']}/verify", headers=H("admin", "halcyon")).status_code == 404
    assert c.get(f"/api/v1/shield/repositories/{env['repo']['id']}/graph", headers=H("admin", "halcyon")).status_code == 404
    assert c.get("/api/v1/shield/hypotheses", headers=H("admin", "halcyon")).json() == []
