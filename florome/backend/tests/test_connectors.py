"""Connector contract: capability declaration, action validation, and the GitHub REST adapter against a mocked transport."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from florome.connectors.base import ActionValidationError, Capability, ConnectorError, UnsupportedCapability
from florome.connectors.github import GitHubConnector
from florome.connectors.registry import NOT_IMPLEMENTED, PLATFORM_CATALOG
from florome.connectors.sandbox import API, JOB, LAMBDA, SandboxConnector
from tests.conftest import H

run = asyncio.run


def test_sandbox_declares_capabilities_and_rejects_undeclared():
    c = SandboxConnector()
    assert Capability.FETCH_INCIDENTS not in c.capabilities()
    assert c.is_simulated
    with pytest.raises(UnsupportedCapability):
        c._require(Capability.FETCH_INCIDENTS)


def test_action_validation():
    c = SandboxConnector()
    assert c.validate_action("rollback_deployment", "lambda", {"to_version": "v2.13.4"}).risk == "medium"
    with pytest.raises(ActionValidationError, match="not in"):
        c.validate_action("rm_rf", "lambda", {})
    with pytest.raises(ActionValidationError, match="does not apply"):
        c.validate_action("rerun_job", "lambda", {})
    with pytest.raises(ActionValidationError, match="Invalid parameters"):
        c.validate_action("rollback_deployment", "lambda", {"to_version": "latest; rm -rf /"})
    with pytest.raises(ActionValidationError, match="Invalid parameters"):
        c.validate_action("rerun_job", "databricks_job", {"extra": 1})


def test_sandbox_rollback_to_wrong_version_fails():
    r = run(SandboxConnector().execute_action("rollback_deployment", LAMBDA, {"to_version": "v1.0.0"}, "k"))
    assert not r.success


def test_sandbox_observations_respect_window_and_kinds():
    c = SandboxConnector()
    now = datetime.now(UTC)
    logs = run(c.fetch_observations(API, now - timedelta(hours=6), now, {"log"}))
    assert logs and {o.kind for o in logs} == {"log"}
    assert run(c.fetch_observations(JOB, now + timedelta(hours=1), now + timedelta(hours=2), {"log", "metric"})) == []


def test_platform_catalog_is_honest(client):
    data = client.get("/api/v1/platforms", headers=H("viewer")).json()["platforms"]
    byp = {p["platform"]: p for p in data}
    assert byp["sandbox"]["connected_and_verified"] is True
    assert byp["github"]["connected_and_verified"] is False
    assert all(not p["connected_and_verified"] for p in data if p["status"] == NOT_IMPLEMENTED)
    assert {"cloudwatch", "azure_devops", "databricks_jobs", "servicenow"} <= {p["platform"] for p in PLATFORM_CATALOG if p["status"] == NOT_IMPLEMENTED}


# ---------------------------------------------------------------------------------------------- GitHub REST

TOKEN = "ghp_testtokentesttokentesttoken1234"


def gh_transport(calls, status_overrides=None):
    now = datetime.now(UTC)

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        key = f"{req.method} {req.url.path}"
        if status_overrides and key in status_overrides:
            return httpx.Response(status_overrides[key])
        if key == "GET /repos/acme/app":
            return httpx.Response(200, json={"full_name": "acme/app"})
        if key == "GET /repos/acme/app/actions/workflows":
            return httpx.Response(200, json={"workflows": [{"id": 7, "name": "CI", "path": ".github/workflows/ci.yml", "state": "active"}]})
        if key == "GET /repos/acme/app/actions/runs":
            return httpx.Response(200, json={"workflow_runs": [
                {"id": 101, "name": "CI", "path": ".github/workflows/ci.yml", "conclusion": "failure", "status": "completed",
                 "head_sha": "abc1234def", "created_at": (now - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")}]})
        if key == "POST /repos/acme/app/issues":
            return httpx.Response(201, json={"number": 42, "html_url": "https://github.example/acme/app/issues/42"})
        if key == "POST /repos/acme/app/actions/runs/101/rerun-failed-jobs":
            return httpx.Response(201)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_github_contract_read_paths():
    calls = []
    gh = GitHubConnector("acme/app", TOKEN, transport=gh_transport(calls))
    assert run(gh.health()).ok
    res = run(gh.discover_resources())
    assert [r.kind for r in res] == ["repository", "ci_pipeline"]
    pipe = res[1].source_ref
    assert run(gh.read_status(pipe))["health"] == "failed"
    now = datetime.now(UTC)
    deps = run(gh.fetch_observations(pipe, now - timedelta(hours=1), now, {"deployment"}))
    assert deps[0].payload["run_id"] == 101
    assert calls[0].headers["authorization"] == f"Bearer {TOKEN}"


def test_github_actions_validate_and_execute():
    calls = []
    gh = GitHubConnector("acme/app", TOKEN, transport=gh_transport(calls))
    gh.validate_action("create_issue", "repository", {"title": "RCA", "body": "evidence"})
    r = run(gh.execute_action("create_issue", "github://acme/app", {"title": "RCA", "body": "evidence"}, "idem-1"))
    assert r.success and r.details["number"] == 42
    assert "idem-1" in json.loads(calls[-1].content)["body"]
    assert run(gh.execute_action("rerun_failed_jobs", "x", {"run_id": 101}, "k")).success


def test_github_without_token_cannot_write():
    gh = GitHubConnector("acme/app", None, transport=gh_transport([]))
    assert Capability.EXECUTE_ACTIONS not in gh.capabilities()
    with pytest.raises(UnsupportedCapability):
        run(gh.execute_action("create_issue", "x", {"title": "abc", "body": ""}, "k"))


def test_github_errors_are_classified_and_never_leak_token():
    gh = GitHubConnector("acme/app", TOKEN, transport=gh_transport([], {"GET /repos/acme/app/actions/workflows": 503,
                                                                         "POST /repos/acme/app/issues": 422}))
    with pytest.raises(ConnectorError) as e1:
        run(gh.discover_resources())
    assert e1.value.retryable and TOKEN not in str(e1.value)
    with pytest.raises(ConnectorError) as e2:
        run(gh.execute_action("create_issue", "x", {"title": "abc", "body": ""}, "k"))
    assert not e2.value.retryable
    assert TOKEN not in repr(gh.__dict__.get("repository"))
