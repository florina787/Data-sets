"""Sandbox connector: a stateful, in-memory simulation of a small multi-cloud estate.

It is the *safe test target* for the whole DETECT -> ... -> VALIDATE loop. Everything it returns is synthetic
and labelled as such (``is_simulated = True``); it never calls any external system.

It is not a mock that returns canned success: each action changes the simulated state according to explicit
causal rules, and an action whose preconditions are not met fails. For example, re-running the Databricks job
while the upstream S3 data is still incomplete fails, exactly as it would in reality. Validation reads the
resulting state, so a wrong or mis-ordered remediation plan is detected.

Scenario ("Cross-cloud revenue reporting outage", all names fictional):

    AWS Lambda ingest-orders -> S3 orders-raw -> Databricks job orders-etl -> Delta gold.revenue_daily
        -> Azure App Service revenue-api -> business process "Daily revenue reporting"

A Lambda deployment switches the payload parser to schema v3, which drops records missing a field. Incomplete
data propagates downstream until the revenue API returns 5xx. Two red herrings are planted: an autoscale
configuration change and an older deployment on revenue-api, plus normal CPU metrics.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

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
from florome.models import utcnow

LAMBDA = "arn:aws:lambda:eu-west-1:000000000000:function:ingest-orders"
BUCKET = "arn:aws:s3:::orders-raw"
JOB = "databricks://workspace-demo/jobs/4711"
TABLE = "databricks://workspace-demo/tables/gold.revenue_daily"
API = "/subscriptions/00000000-demo/resourceGroups/rg-revenue/providers/Microsoft.Web/sites/revenue-api"
PROCESS = "business://finance/daily-revenue-reporting"
PIPELINE = "github://demo-org/revenue-api/actions/workflows/deploy.yml"
PORTAL = "/subscriptions/00000000-demo/resourceGroups/rg-portal/providers/Microsoft.Web/sites/customer-portal"
AGENT = "aws://bedrock/agents/support-copilot"
KB = "aws://bedrock/knowledge-bases/support-kb"
MCP_SRV = "mcp://sandbox-ops"

RESOURCES: list[ResourceRecord] = [
    ResourceRecord(LAMBDA, "lambda", "ingest-orders", "aws", attributes={"runtime": "python3.12", "version": "v2.14.0", "region": "eu-west-1"}),
    ResourceRecord(BUCKET, "s3_bucket", "orders-raw", "aws", attributes={"region": "eu-west-1"}),
    ResourceRecord(JOB, "databricks_job", "orders-etl", "databricks", attributes={"job_id": 4711, "schedule": "every 15 min"}),
    ResourceRecord(TABLE, "delta_table", "gold.revenue_daily", "databricks", attributes={"catalog": "main", "freshness_slo_minutes": 90}),
    ResourceRecord(API, "app_service", "revenue-api", "azure", attributes={"region": "westeurope", "version": "v3.2.0"}),
    ResourceRecord(PROCESS, "business_process", "Daily revenue reporting", "business", attributes={"owner": "Finance", "sla": "07:00 UTC"}),
    ResourceRecord(PIPELINE, "ci_pipeline", "revenue-api deploy", "github", attributes={"repository": "demo-org/revenue-api"}),
    ResourceRecord(PORTAL, "app_service", "customer-portal", "azure", attributes={"region": "westeurope"}),
    ResourceRecord(AGENT, "ai_agent", "support-copilot", "aws", attributes={"framework": "Bedrock Agents"}),
    ResourceRecord(KB, "knowledge_base", "support-kb", "aws"),
    ResourceRecord(MCP_SRV, "mcp_server", "sandbox-ops MCP server", "mcp", attributes={"transport": "stdio"}),
]
# (source, target, kind): data or calls flow source -> target
DEPENDENCIES: list[tuple[str, str, str]] = [
    (LAMBDA, BUCKET, "data_flow"),
    (BUCKET, JOB, "data_flow"),
    (JOB, TABLE, "data_flow"),
    (TABLE, API, "data_flow"),
    (API, PROCESS, "serves"),
    (PIPELINE, API, "deploys"),
    (KB, AGENT, "retrieval"),
    (AGENT, PORTAL, "serves"),
    (MCP_SRV, AGENT, "tools"),
]
PREVIOUS_VERSION = {LAMBDA: "v2.13.4", API: "v3.1.9"}


def _a(action_id: str, title: str, desc: str, kinds: tuple[str, ...], schema: dict, risk: str, reversible: bool, rollback: str,
       perm: str, outcome: str) -> ActionSpec:
    return ActionSpec(action_id, title, desc, kinds, {"type": "object", "additionalProperties": False, **schema}, risk, reversible,
                      rollback, perm, outcome, tested=True)


ACTIONS: list[ActionSpec] = [
    _a("rollback_deployment", "Roll back deployment", "Point the service alias back to the previous known-good version.",
       ("lambda", "app_service"), {"properties": {"to_version": {"type": "string", "pattern": r"^v\d+\.\d+\.\d+$"}}, "required": ["to_version"]},
       "medium", True, "Re-point the alias to the rolled-back version (the deployment artefact is retained).",
       "lambda:UpdateAlias / Microsoft.Web/sites/slots/swap", "Error rate on the target returns below threshold."),
    _a("replay_ingestion", "Replay ingestion window", "Re-ingest source records for a bounded time window (idempotent upserts).",
       ("lambda",), {"properties": {"window_minutes": {"type": "integer", "minimum": 1, "maximum": 1440}}, "required": ["window_minutes"]},
       "medium", True, "Upserts are keyed by order id, so a replay cannot duplicate; stop the replay to halt.",
       "lambda:InvokeFunction", "Object volume in the landing bucket returns to baseline."),
    _a("rerun_job", "Re-run job", "Trigger a new run of the job with its current definition.",
       ("databricks_job",), {"properties": {}}, "medium", True, "Delta table versions allow RESTORE TABLE to the prior version.",
       "CAN_MANAGE_RUN on the job", "Job run succeeds and the target table is refreshed."),
    _a("refresh_cache", "Refresh application cache", "Invalidate the service's read-through cache so it re-reads source tables.",
       ("app_service",), {"properties": {}}, "low", True, "No rollback needed; the cache repopulates from source.",
       "Microsoft.Web/sites/restart/action (scoped)", "HTTP 5xx rate returns below threshold."),
    _a("create_ticket", "Create incident ticket", "Open a ticket with the RCA summary attached.",
       ("lambda", "s3_bucket", "databricks_job", "delta_table", "app_service", "business_process", "ci_pipeline"),
       {"properties": {"summary": {"type": "string", "maxLength": 500}}, "required": ["summary"]}, "low", True,
       "Close the ticket.", "ticket:create", "A ticket reference is returned."),
]

@dataclass
class _State:
    health: dict[str, str] = field(default_factory=dict)
    version: dict[str, str] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    executed: dict[str, ActionResult] = field(default_factory=dict)  # idempotency_key -> result
    fail_next: dict[str, list[bool]] = field(default_factory=dict)  # action_id -> [retryable flags] for fault injection
    delay: dict[str, float] = field(default_factory=dict)  # action_id -> seconds (timeout tests)
    tickets: list[dict[str, Any]] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)


class SandboxWorld:
    def __init__(self, anchor: datetime | None = None):
        self.anchor = anchor or utcnow()
        self.s = _State()
        self.reset()

    def reset(self) -> None:
        self.s = _State()
        for r in RESOURCES:
            self.s.health[r.source_ref] = "healthy"
            if "version" in r.attributes:
                self.s.version[r.source_ref] = r.attributes["version"]
        for ref in (LAMBDA, BUCKET, JOB, TABLE, API, PROCESS):
            self.s.health[ref] = "failed" if ref in (LAMBDA, JOB, API) else "degraded"
        self._seed_observations()

    def t(self, minutes: float) -> datetime:
        return self.anchor + timedelta(minutes=minutes)

    def _obs(self, kind: str, ref: str, minute: float, summary: str, payload: dict[str, Any]) -> None:
        idx = len(self.s.observations)
        self.s.observations.append(Observation(kind, ref, self.t(minute), summary, payload, f"sandbox-obs-{idx:04d}"))

    def _seed_observations(self) -> None:
        o = self._obs
        # Red herring 1: an old revenue-api deployment, three hours before.
        o("deployment", API, -180, "revenue-api v3.2.0 deployed by GitHub Actions run 9123",
          {"version": "v3.2.0", "previous_version": "v3.1.9", "deployed_by": "github-actions", "signature_terms": ["RevenueFormatter", "v3.2.0"]})
        # Red herring 2: an autoscale configuration change on the symptomatic service.
        o("config_change", API, -75, "Autoscale minimum instances changed 2 -> 3",
          {"setting": "autoscale.min_instances", "old": 2, "new": 3, "changed_by": "platform-team",
           "signature_terms": ["autoscale", "min_instances", "instance count"]})
        # The actual change.
        o("deployment", LAMBDA, -50, "ingest-orders v2.14.0 deployed: switch order payload parser to schema v3",
          {"version": "v2.14.0", "previous_version": "v2.13.4", "deployed_by": "aws-codedeploy",
           "change": "OrderSchemaV3 parser", "signature_terms": ["OrderSchemaV3", "schema v3"]})
        for m in (-48, -40, -32, -24, -16):
            o("log", LAMBDA, m, "OrderSchemaV3 validation failed: required field 'currency' missing; record dropped",
              {"level": "ERROR", "message": "OrderSchemaV3 validation failed: required field 'currency' missing; record dropped",
               "count": 80 + int(-m)})
        o("metric", LAMBDA, -45, "Errors 412 per 5 min (threshold 5)",
          {"name": "Errors", "value": 412, "threshold": 5, "direction": "above", "unit": "count/5min"})
        o("metric", BUCKET, -45, "Objects written 38 per 15 min (baseline minimum 120)",
          {"name": "ObjectsWritten", "value": 38, "threshold": 120, "direction": "below", "unit": "count/15min"})
        o("metric", JOB, -33, "Cluster CPU 41% (threshold 85%)",
          {"name": "cpu_percent", "value": 41, "threshold": 85, "direction": "above", "capacity": True, "unit": "%"})
        o("log", JOB, -30, "Run 88412 failed: data quality check on orders-raw partition 2026-11-10 row count 18,240 below expected minimum 45,000",
          {"level": "ERROR", "run_id": 88412,
           "message": "Data quality check failed: orders-raw partition row count 18,240 below expected minimum 45,000 (40.5%)"})
        o("log", TABLE, -26, "gold.revenue_daily not updated: last write by orders-etl run 88398 (successful) at T-46m",
          {"level": "ERROR", "message": "Freshness SLO breached for gold.revenue_daily; upstream orders-etl run 88412 did not commit"})
        o("metric", TABLE, -25, "Freshness 136 minutes (SLO 90)",
          {"name": "freshness_minutes", "value": 136, "threshold": 90, "direction": "above", "unit": "min"})
        o("metric", API, -22, "Cluster CPU 35% (threshold 80%)",
          {"name": "cpu_percent", "value": 35, "threshold": 80, "direction": "above", "capacity": True, "unit": "%"})
        o("log", API, -20, "500 InternalServerError: RevenueSummaryService: gold.revenue_daily returned 0 rows for business_date=2026-11-10",
          {"level": "ERROR", "message": "RevenueSummaryService: gold.revenue_daily returned 0 rows for business_date=2026-11-10", "status": 500})
        o("metric", API, -18, "HTTP 5xx rate 23.4% (threshold 2%)",
          {"name": "http_5xx_rate", "value": 23.4, "threshold": 2, "direction": "above", "unit": "%"})
        o("trace", API, -18, "GET /v1/revenue/summary 500 in 312 ms; span 'query gold.revenue_daily' returned 0 rows",
          {"trace_id": "4bf92f3577b34da6a3ce929d0e0e4736", "status": 500, "duration_ms": 312})
        o("status", PROCESS, -5, "Report generation blocked: revenue-api returned errors for 3 consecutive attempts",
          {"level": "ERROR", "message": "Daily revenue report blocked: revenue-api returned errors", "attempts": 3})

    # -------------------------------------------------------------------------------------- causal action model

    def apply(self, action_id: str, ref: str, params: dict[str, Any]) -> ActionResult:
        h = self.s.health
        if action_id == "rollback_deployment":
            expected = PREVIOUS_VERSION.get(ref)
            if params["to_version"] != expected:
                return ActionResult(False, f"Version {params['to_version']} is not the previous known-good version ({expected})")
            self.s.version[ref] = expected
            if ref == LAMBDA:
                h[LAMBDA] = "healthy"
                return ActionResult(True, f"ingest-orders alias now points to {expected}; no new validation errors", {"version": expected})
            return ActionResult(True, f"revenue-api swapped to {expected}", {"version": expected, "note": "did not change data freshness"})
        if action_id == "replay_ingestion":
            if h[LAMBDA] != "healthy":
                return ActionResult(False, "Replay rejected records again: OrderSchemaV3 validation failed (parser still faulty)")
            h[BUCKET] = "healthy"
            return ActionResult(True, f"Replayed {params['window_minutes']} min of orders; 46,120 objects written", {"objects": 46120})
        if action_id == "rerun_job":
            if h[BUCKET] != "healthy":
                return ActionResult(False, "Run failed: data quality check on orders-raw (row count below minimum)")
            h[JOB] = "healthy"
            h[TABLE] = "healthy"
            return ActionResult(True, "Run 88431 succeeded; gold.revenue_daily committed version 1207", {"run_id": 88431})
        if action_id == "refresh_cache":
            if h[TABLE] != "healthy":
                return ActionResult(False, "Cache refreshed but source table is still stale; 5xx persists")
            h[API] = "healthy"
            h[PROCESS] = "healthy"
            return ActionResult(True, "Cache invalidated; /v1/revenue/summary returns 200", {})
        if action_id == "create_ticket":
            ticket = {"id": f"SBX-{1000 + len(self.s.tickets)}", "resource": ref, "summary": params["summary"]}
            self.s.tickets.append(ticket)
            return ActionResult(True, f"Ticket {ticket['id']} created (sandbox)", ticket)
        raise ConnectorError(f"Unknown action {action_id}")

    def verify(self, ref: str) -> VerificationResult:
        name = next(r.name for r in RESOURCES if r.source_ref == ref)
        state = self.s.health[ref]
        checks = [{"check": "health_state", "resource": name, "observed": state, "expected": "healthy", "passed": state == "healthy"}]
        metric = {LAMBDA: ("Errors", 0 if state == "healthy" else 398, 5, "above"),
                  BUCKET: ("ObjectsWritten", 151 if state == "healthy" else 36, 120, "below"),
                  TABLE: ("freshness_minutes", 4 if state == "healthy" else 141, 90, "above"),
                  API: ("http_5xx_rate", 0.1 if state == "healthy" else 22.9, 2, "above")}.get(ref)
        if metric:
            n, v, thr, d = metric
            ok = v < thr if d == "above" else v >= thr
            checks.append({"check": f"metric:{n}", "resource": name, "observed": v, "threshold": thr, "direction": d, "passed": ok})
        if ref == PROCESS:
            checks.append({"check": "business_outcome", "resource": name, "observed": "report generated" if state == "healthy" else "blocked",
                           "expected": "report generated", "passed": state == "healthy"})
        return VerificationResult(all(c["passed"] for c in checks), checks)


class SandboxConnector(Connector):
    connector_type = "sandbox"
    platform = "sandbox"
    is_simulated = True

    def __init__(self, world: SandboxWorld | None = None):
        self.world = world or SandboxWorld()

    def capabilities(self) -> set[Capability]:
        return {Capability.DISCOVER_RESOURCES, Capability.READ_STATUS, Capability.FETCH_LOGS, Capability.FETCH_METRICS,
                Capability.FETCH_TRACES, Capability.FETCH_DEPLOYMENTS, Capability.FETCH_CHANGES, Capability.LIST_ACTIONS,
                Capability.EXECUTE_ACTIONS, Capability.VERIFY}

    async def health(self) -> HealthResult:
        return HealthResult(True, "Sandbox simulation reachable (synthetic, no external calls)", ["discover_resources", "read_status"])

    async def discover_resources(self) -> list[ResourceRecord]:
        return list(RESOURCES)

    async def read_status(self, resource_ref: str) -> dict[str, Any]:
        return {"health": self.world.s.health[resource_ref], "version": self.world.s.version.get(resource_ref)}

    async def fetch_observations(self, resource_ref: str, start: datetime, end: datetime, kinds: set[str]) -> list[Observation]:
        return [o for o in self.world.s.observations
                if o.resource_ref == resource_ref and start <= o.observed_at <= end and o.kind in kinds]

    def list_actions(self) -> list[ActionSpec]:
        return list(ACTIONS)

    async def execute_action(self, action_id: str, resource_ref: str, params: dict[str, Any], idempotency_key: str) -> ActionResult:
        s = self.world.s
        if idempotency_key in s.executed:
            prev = s.executed[idempotency_key]
            return ActionResult(prev.success, prev.message, prev.details, idempotent_replay=True)
        s.calls.append((action_id, resource_ref))
        if s.delay.get(action_id):
            await asyncio.sleep(s.delay[action_id])
        if s.fail_next.get(action_id):
            retryable = s.fail_next[action_id].pop(0)
            raise ConnectorError(f"Injected {'transient' if retryable else 'permanent'} failure for {action_id}", retryable=retryable)
        result = self.world.apply(action_id, resource_ref, params)
        if result.success:
            s.executed[idempotency_key] = result
        return result

    async def verify(self, resource_ref: str) -> VerificationResult:
        return self.world.verify(resource_ref)
