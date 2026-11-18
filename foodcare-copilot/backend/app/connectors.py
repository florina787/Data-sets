"""Enterprise connectors: honest status, governed read-only adapters, no invented connections.

Each connector reports one of these states, and only from evidence:
  planned · adapter_available · configured · connection_tested · connected · read_only ·
  write_with_approval · simulated · failed
A connector is never "connected" because a settings screen exists: Databricks and Kubernetes
become ``configured`` only when their environment variables are present, and
``connection_tested`` / ``failed`` only after a real request.

Governance for every external call (:func:`governed_call`): an allowlisted operation, a timeout,
a per-user rate limit, a circuit breaker, one safe retry for idempotent reads, an audit record
with counts only, and output passed through :func:`neutralise` (tool output is untrusted data).
There is no write path and no free-form SQL or kubectl from conversations.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from app.db import now_iso

STATES = (
    "planned",
    "adapter_available",
    "configured",
    "connection_tested",
    "connected",
    "read_only",
    "write_with_approval",
    "simulated",
    "failed",
)


# --- governance ---------------------------------------------------------------------------


@dataclass
class Breaker:
    failures: int = 0
    opened_at: float | None = None
    threshold: int = 3
    cool_down_s: float = 60.0

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        if time.monotonic() - self.opened_at > self.cool_down_s:
            self.opened_at, self.failures = None, 0
            return True
        return False

    def record(self, ok: bool) -> None:
        if ok:
            self.failures, self.opened_at = 0, None
        else:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = time.monotonic()


@dataclass
class Governor:
    breakers: dict[str, Breaker] = field(default_factory=dict)
    calls: dict[tuple[str, str], list[float]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)
    per_minute: int = 30


GOV = Governor()


class ConnectorError(Exception):
    pass


_INJECTION = re.compile(
    r"(ignore (all |any )?(previous|prior|above) instructions|disregard .{0,30}instructions|"
    r"you are now|system prompt|reveal .{0,20}(secret|password|key|prompt)|"
    r"<\s*/?\s*(system|tool)\s*>)",
    re.I,
)


def neutralise(value, max_len: int = 2000):
    """Tool output is data, never instructions: strip instruction-like text and cap sizes."""
    from app import privacy

    if isinstance(value, str):
        return privacy.scrub(_INJECTION.sub("[instruction-like text removed]", value))[:max_len]
    if isinstance(value, dict):
        return {k: neutralise(v, max_len) for k, v in list(value.items())[:200]}
    if isinstance(value, list):
        return [neutralise(v, max_len) for v in value[:500]]
    return value


def governed_call(connector: str, operation: str, username: str, fn, *, idempotent: bool = True):
    with GOV.lock:
        br = GOV.breakers.setdefault(connector, Breaker())
        if not br.allow():
            raise ConnectorError(f"{connector} is temporarily paused after repeated failures (circuit open)")
        now = time.monotonic()
        recent = [t for t in GOV.calls.get((connector, username), []) if now - t < 60]
        if len(recent) >= GOV.per_minute:
            raise ConnectorError(f"Rate limit reached for {connector}; try again in a minute")
        GOV.calls[(connector, username)] = recent + [now]
    attempts = 2 if idempotent else 1
    last: Exception | None = None
    for _ in range(attempts):
        try:
            result = neutralise(fn())
            with GOV.lock:
                br.record(True)
            _audit(username, connector, operation, "ok")
            return result
        except (httpx.HTTPError, ConnectorError) as exc:
            last = exc
    with GOV.lock:
        br.record(False)
    _audit(username, connector, operation, "failed")
    raise ConnectorError(f"{connector} {operation} failed: {type(last).__name__}") from last


def _audit(username: str, connector: str, operation: str, outcome: str) -> None:
    try:
        from app.records import audit

        audit(
            username,
            f"connector.{connector}",
            outcome=outcome,
            entity_type="connector",
            entity_id=connector,
            operation=operation,
        )
    except Exception:  # noqa: BLE001
        pass


# --- Databricks (read-only SQL Statement Execution API, allowlisted queries) ----------------

DATABRICKS_QUERIES: dict[str, tuple[str, dict[str, str]]] = {
    # name -> (parameterised SELECT, {param: type}); the catalog/schema come from configuration.
    "factory_performance": (
        "SELECT site, week, throughput_units, downtime_hours, oee_pct FROM {schema}.factory_weekly "
        "WHERE week >= :since ORDER BY site, week",
        {"since": "DATE"},
    ),
    "supplier_quality": (
        "SELECT supplier_id, week, lots_received, lots_rejected FROM {schema}.supplier_quality WHERE week >= :since",
        {"since": "DATE"},
    ),
    "table_freshness": (
        "SELECT table_name, last_altered FROM system.information_schema.tables WHERE table_schema = :schema_name",
        {"schema_name": "STRING"},
    ),
}


def databricks_config() -> dict | None:
    host, token, wh = (
        os.environ.get("DATABRICKS_HOST"),
        os.environ.get("DATABRICKS_TOKEN"),
        os.environ.get("DATABRICKS_WAREHOUSE_ID"),
    )
    if not (host and token and wh):
        return None
    return {
        "host": host.rstrip("/"),
        "token": token,
        "warehouse_id": wh,
        "schema": os.environ.get("DATABRICKS_SCHEMA", "main.foodcare"),
    }


def databricks_query(name: str, params: dict, username: str) -> dict:
    """Run an allowlisted, parameterised query. No LLM-written SQL is ever executed."""
    if name not in DATABRICKS_QUERIES:
        raise ConnectorError("Query is not on the Databricks allowlist")
    cfg = databricks_config()
    if not cfg:
        raise ConnectorError(
            "Databricks is not configured (DATABRICKS_HOST, DATABRICKS_TOKEN, DATABRICKS_WAREHOUSE_ID)"
        )
    sql, types = DATABRICKS_QUERIES[name]
    if set(params) != set(types):
        raise ConnectorError("Query parameters do not match the allowlisted signature")
    if not re.fullmatch(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", cfg["schema"]):
        raise ConnectorError("Invalid schema name in configuration")

    def call() -> dict:
        r = httpx.post(
            f"{cfg['host']}/api/2.0/sql/statements",
            timeout=20,
            headers={"Authorization": f"Bearer {cfg['token']}"},
            json={
                "warehouse_id": cfg["warehouse_id"],
                "statement": sql.format(schema=cfg["schema"]),
                "parameters": [{"name": k, "value": str(v), "type": types[k]} for k, v in params.items()],
                "wait_timeout": "15s",
                "disposition": "INLINE",
                "format": "JSON_ARRAY",
            },
        )
        r.raise_for_status()
        body = r.json()
        if body.get("status", {}).get("state") != "SUCCEEDED":
            raise ConnectorError(f"statement {body.get('status', {}).get('state', 'unknown')}")
        cols = [c["name"] for c in body["manifest"]["schema"]["columns"]]
        data = body["result"].get("data_array", [])
        return {
            "columns": cols,
            "rows": [dict(zip(cols, r_, strict=False)) for r_ in data],
            "query": name,
            "fetched_at": now_iso(),
        }

    return governed_call("databricks", name, username, call)


# --- Kubernetes (read-only API, allowlisted namespaces) ------------------------------------

SA_DIR = Path("/var/run/secrets/kubernetes.io/serviceaccount")


def kubernetes_config() -> dict | None:
    url = os.environ.get("FOODCARE_K8S_API_URL")
    token = os.environ.get("FOODCARE_K8S_TOKEN")
    if not url and os.environ.get("KUBERNETES_SERVICE_HOST") and (SA_DIR / "token").exists():
        url = f"https://{os.environ['KUBERNETES_SERVICE_HOST']}:{os.environ.get('KUBERNETES_SERVICE_PORT', '443')}"
        token = (SA_DIR / "token").read_text().strip()
    if not (url and token):
        return None
    ns = [n for n in os.environ.get("FOODCARE_K8S_NAMESPACES", "foodcare").split(",") if n]
    verify: str | bool = str(SA_DIR / "ca.crt") if (SA_DIR / "ca.crt").exists() else True
    if os.environ.get("FOODCARE_K8S_CA"):
        verify = os.environ["FOODCARE_K8S_CA"]
    return {"url": url.rstrip("/"), "token": token, "namespaces": ns, "verify": verify}


def kubernetes_health(username: str, namespace: str | None = None) -> dict:
    """Deployment and pod health for allowlisted namespaces. GET only; no exec, no secrets, no writes."""
    cfg = kubernetes_config()
    if not cfg:
        raise ConnectorError("Kubernetes is not configured (in-cluster service account or FOODCARE_K8S_API_URL)")
    namespaces = [namespace] if namespace else cfg["namespaces"]
    if any(n not in cfg["namespaces"] for n in namespaces):
        raise ConnectorError("Namespace is not on the allowlist")

    def call() -> dict:
        h = {"Authorization": f"Bearer {cfg['token']}"}
        out = []
        with httpx.Client(timeout=10, verify=cfg["verify"], headers=h) as c:
            for ns in namespaces:
                deps = c.get(f"{cfg['url']}/apis/apps/v1/namespaces/{ns}/deployments")
                deps.raise_for_status()
                pods = c.get(f"{cfg['url']}/api/v1/namespaces/{ns}/pods")
                pods.raise_for_status()
                for d in deps.json().get("items", []):
                    spec, st = d.get("spec", {}), d.get("status", {})
                    out.append(
                        {
                            "namespace": ns,
                            "deployment": d["metadata"]["name"],
                            "desired": spec.get("replicas", 0),
                            "ready": st.get("readyReplicas", 0),
                            "updated": st.get("updatedReplicas", 0),
                        }
                    )
                restarts = [
                    {
                        "namespace": ns,
                        "pod": p["metadata"]["name"],
                        "phase": p.get("status", {}).get("phase"),
                        "restarts": sum(
                            cs.get("restartCount", 0) for cs in p.get("status", {}).get("containerStatuses", [])
                        ),
                    }
                    for p in pods.json().get("items", [])
                ]
        # Only names, counts and phases leave this function: no env, annotations, images or secrets.
        return {"deployments": out, "pods": restarts, "fetched_at": now_iso()}

    return governed_call("kubernetes", "health", username, call)


# --- registry ---------------------------------------------------------------------------------


def _llm_state() -> tuple[str, str]:
    from app.llm import local

    s = local.status()
    if not s.get("configured"):
        return "adapter_available", "Set FOODCARE_LLM_BASE_URL and FOODCARE_LLM_MODEL to use your local Qwen."
    return ("connected", "Reachable") if s.get("reachable") else ("failed", "Configured but not reachable")


_TESTS: dict[str, dict] = {}


def test_connection(connector_id: str, username: str) -> dict:
    try:
        if connector_id == "databricks":
            schema = (databricks_config() or {}).get("schema", "x").split(".")[-1]
            databricks_query("table_freshness", {"schema_name": schema}, username)
        elif connector_id == "kubernetes":
            kubernetes_health(username)
        else:
            raise ConnectorError("This connector has no live test")
        _TESTS[connector_id] = {"at": now_iso(), "ok": True, "detail": "Read-only test request succeeded"}
    except ConnectorError as exc:
        _TESTS[connector_id] = {"at": now_iso(), "ok": False, "detail": str(exc)}
    return _TESTS[connector_id]


def registry() -> list[dict]:
    llm_state, llm_detail = _llm_state()

    def tested(cid: str, configured: bool) -> tuple[str, str]:
        if not configured:
            return "adapter_available", "Adapter built and contract-tested against a mock; no credentials configured."
        t = _TESTS.get(cid)
        if not t:
            return "configured", "Credentials present; run a connection test."
        return ("connection_tested", t["detail"]) if t["ok"] else ("failed", t["detail"])

    db_state, db_detail = tested("databricks", databricks_config() is not None)
    k8_state, k8_detail = tested("kubernetes", kubernetes_config() is not None)
    planned = "No adapter yet. Needs a read-only service account and an approved schema mapping."
    items = [
        (
            "demo_data",
            "Enterprise demo dataset (SQLite)",
            "Built-in",
            "connected",
            "Synthetic sales, stock, compliance, suppliers. Read-only to Jerry.",
            "read",
        ),
        (
            "app_records",
            "Operational records (this app)",
            "Built-in",
            "connected",
            "Inspections, incidents, deployments, agent runs, decisions.",
            "read",
        ),
        ("local_llm", "Local model (Qwen via OpenAI-compatible API)", "AI", llm_state, llm_detail, "read"),
        (
            "mcp_server",
            "Flo & Jerry MCP server (/mcp)",
            "MCP",
            "read_only",
            "Exposes approved, policy-filtered read-only tools to MCP clients (JSON-RPC 2.0).",
            "read",
        ),
        ("databricks", "Databricks SQL (governed analytics)", "Analytics", db_state, db_detail, "read"),
        ("kubernetes", "Kubernetes API (service health)", "Infrastructure", k8_state, k8_detail, "read"),
        (
            "prometheus",
            "Prometheus /metrics",
            "Observability",
            "read_only",
            "This app publishes metrics for your Prometheus/Grafana to scrape.",
            "read",
        ),
        ("sap_erp", "SAP / ERP (purchasing, inventory)", "Legacy", "planned", planned, "none"),
        ("oracle", "Oracle-style systems", "Legacy", "planned", planned, "none"),
        ("sqlserver", "SQL Server", "Database", "planned", planned, "none"),
        ("postgres", "PostgreSQL", "Database", "planned", planned, "none"),
        ("rest", "REST APIs", "API", "planned", planned, "none"),
        ("soap", "SOAP services", "API", "planned", planned, "none"),
        ("lake", "Data lake / object storage", "Storage", "planned", planned, "none"),
        (
            "documents",
            "Enterprise documents",
            "Content",
            "connected",
            "Built-in policy documents (BM25 search).",
            "read",
        ),
        ("events", "Event streams", "Streaming", "planned", planned, "none"),
    ]
    return [
        {
            "id": i,
            "name": n,
            "category": c,
            "state": s,
            "detail": d,
            "access": a,
            "last_test": _TESTS.get(i),
            "setup": SETUP.get(i),
        }
        for i, n, c, s, d, a in items
    ]


SETUP = {
    "databricks": {
        "env": ["DATABRICKS_HOST", "DATABRICKS_TOKEN", "DATABRICKS_WAREHOUSE_ID", "DATABRICKS_SCHEMA"],
        "auth": "Service principal or token with USE + SELECT on the approved schema only (Unity Catalog).",
        "scope": "Read-only. Allowlisted, parameterised queries: " + ", ".join(DATABRICKS_QUERIES) + ".",
    },
    "kubernetes": {
        "env": ["FOODCARE_K8S_API_URL", "FOODCARE_K8S_TOKEN", "FOODCARE_K8S_NAMESPACES"],
        "auth": "In-cluster ServiceAccount bound to a Role with get/list on deployments and pods only.",
        "scope": "Read-only, allowlisted namespaces. No exec, logs, secrets or writes.",
    },
    "local_llm": {
        "env": ["FOODCARE_LLM_BASE_URL", "FOODCARE_LLM_MODEL"],
        "auth": "None for a local server; optional FOODCARE_LLM_API_KEY for a gateway.",
        "scope": "Receives only policy-filtered facts and citations.",
    },
}
