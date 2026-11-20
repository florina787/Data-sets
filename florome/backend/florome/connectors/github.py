"""GitHub REST connector (direct REST, no MCP).

Implements the connector contract against documented GitHub REST endpoints:

  GET  /repos/{repo}                                  health / discover
  GET  /repos/{repo}/actions/workflows                discover CI pipelines
  GET  /repos/{repo}/actions/runs?per_page=...        deployment history (workflow runs)
  POST /repos/{repo}/actions/runs/{id}/rerun-failed-jobs   action: rerun_failed_jobs
  POST /repos/{repo}/issues                           action: create_issue

Status: contract-tested against a mocked HTTP transport only. It is reported as *verified* only after
``health()`` succeeds against the real API with a token supplied via FLOROME_GITHUB_TOKEN. The token is held
in this object, sent only in the Authorization header to the configured API host, and never returned.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from florome.connectors.base import (
    ActionResult,
    ActionSpec,
    Capability,
    Connector,
    ConnectorError,
    HealthResult,
    Observation,
    ResourceRecord,
    VerificationResult,
)

ACTIONS = [
    ActionSpec("rerun_failed_jobs", "Re-run failed workflow jobs", "Re-run only the failed jobs of a workflow run.",
               ("ci_pipeline",), {"type": "object", "additionalProperties": False,
                                  "properties": {"run_id": {"type": "integer", "minimum": 1}}, "required": ["run_id"]},
               "low", True, "Cancel the re-run; no repository state changes.", "actions:write",
               "The re-run completes with conclusion 'success'.", tested=True),
    ActionSpec("create_issue", "Open issue with diagnostic evidence", "Create an issue containing the RCA summary.",
               ("repository", "ci_pipeline"), {"type": "object", "additionalProperties": False,
                                               "properties": {"title": {"type": "string", "minLength": 3, "maxLength": 200},
                                                              "body": {"type": "string", "maxLength": 20000}},
                                               "required": ["title", "body"]},
               "low", True, "Close the issue.", "issues:write", "An issue number is returned.", tested=True),
]


class GitHubConnector(Connector):
    connector_type = "github_rest"
    platform = "github"

    def __init__(self, repository: str, token: str | None, api_url: str = "https://api.github.com",
                 transport: httpx.AsyncBaseTransport | None = None, timeout: float = 10.0):
        if "/" not in repository:
            raise ValueError("repository must be 'owner/name'")
        self.repository = repository
        self._token = token
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "florome-connector"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(base_url=api_url, headers=headers, timeout=timeout, transport=transport)

    def capabilities(self) -> set[Capability]:
        caps = {Capability.DISCOVER_RESOURCES, Capability.READ_STATUS, Capability.FETCH_DEPLOYMENTS, Capability.LIST_ACTIONS}
        if self._token:  # writes need an authenticated identity
            caps |= {Capability.EXECUTE_ACTIONS, Capability.VERIFY}
        return caps

    async def _req(self, method: str, path: str, **kw: Any) -> Any:
        try:
            r = await self._client.request(method, path, **kw)
        except httpx.TimeoutException as exc:
            raise ConnectorError(f"GitHub {method} {path} timed out", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ConnectorError(f"GitHub {method} {path} failed: {type(exc).__name__}", retryable=True) from exc
        if r.status_code in (429, 500, 502, 503, 504):
            raise ConnectorError(f"GitHub {method} {path} -> {r.status_code}", retryable=True)
        if r.status_code == 403 and r.headers.get("x-ratelimit-remaining") == "0":
            raise ConnectorError("GitHub rate limit exhausted", retryable=True)
        if r.status_code >= 400:
            raise ConnectorError(f"GitHub {method} {path} -> {r.status_code}")
        return r.json() if r.content else {}

    async def health(self) -> HealthResult:
        try:
            repo = await self._req("GET", f"/repos/{self.repository}")
        except ConnectorError as exc:
            return HealthResult(False, str(exc))
        return HealthResult(True, f"Read access to {repo.get('full_name', self.repository)} confirmed", ["GET /repos/{repo}"])

    async def discover_resources(self) -> list[ResourceRecord]:
        data = await self._req("GET", f"/repos/{self.repository}/actions/workflows")
        out = [ResourceRecord(f"github://{self.repository}", "repository", self.repository, "github")]
        for wf in data.get("workflows", []):
            out.append(ResourceRecord(f"github://{self.repository}/actions/workflows/{wf['path'].rsplit('/', 1)[-1]}", "ci_pipeline",
                                      wf.get("name", wf["path"]), "github", attributes={"workflow_id": wf["id"], "state": wf.get("state")}))
        return out

    async def _runs(self, per_page: int = 30) -> list[dict[str, Any]]:
        data = await self._req("GET", f"/repos/{self.repository}/actions/runs", params={"per_page": per_page})
        return data.get("workflow_runs", [])

    async def read_status(self, resource_ref: str) -> dict[str, Any]:
        runs = [r for r in await self._runs(10) if resource_ref.endswith(r.get("path", "").rsplit("/", 1)[-1])]
        if not runs:
            return {"health": "unknown", "detail": "no runs found"}
        latest = runs[0]
        health = {"success": "healthy", "failure": "failed", None: "running"}.get(latest.get("conclusion"), "degraded")
        return {"health": health, "run_id": latest["id"], "conclusion": latest.get("conclusion")}

    async def fetch_observations(self, resource_ref: str, start: datetime, end: datetime, kinds: set[str]) -> list[Observation]:
        if "deployment" not in kinds:
            return []
        out = []
        for r in await self._runs(50):
            ts = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            if not (start <= ts <= end) or not resource_ref.endswith(r.get("path", "").rsplit("/", 1)[-1]):
                continue
            out.append(Observation("deployment", resource_ref, ts, f"{r.get('name')} run {r['id']}: {r.get('conclusion') or r.get('status')}",
                                   {"run_id": r["id"], "head_sha": r.get("head_sha"), "conclusion": r.get("conclusion"),
                                    "signature_terms": [r.get("head_sha", "")[:7]]}, str(r["id"])))
        return out

    def list_actions(self) -> list[ActionSpec]:
        return list(ACTIONS)

    async def execute_action(self, action_id: str, resource_ref: str, params: dict[str, Any], idempotency_key: str) -> ActionResult:
        self._require(Capability.EXECUTE_ACTIONS)
        if action_id == "rerun_failed_jobs":
            await self._req("POST", f"/repos/{self.repository}/actions/runs/{params['run_id']}/rerun-failed-jobs")
            return ActionResult(True, f"Re-run of failed jobs requested for run {params['run_id']}", {"run_id": params["run_id"]})
        if action_id == "create_issue":
            body = params["body"] + f"\n\n<!-- florome-idempotency-key: {idempotency_key} -->"
            data = await self._req("POST", f"/repos/{self.repository}/issues", json={"title": params["title"], "body": body})
            return ActionResult(True, f"Issue #{data.get('number')} created", {"number": data.get("number"), "url": data.get("html_url")})
        raise ConnectorError(f"Unknown action {action_id}")

    async def verify(self, resource_ref: str) -> VerificationResult:
        st = await self.read_status(resource_ref)
        return VerificationResult(st["health"] == "healthy",
                                  [{"check": "latest_run_conclusion", "observed": st.get("conclusion"), "expected": "success",
                                    "passed": st["health"] == "healthy"}])

    async def aclose(self) -> None:
        await self._client.aclose()
