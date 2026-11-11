# Architecture

```mermaid
flowchart TB
  UI[React UI<br/>Vite · Tailwind · React Flow · ECharts] -->|/api/v1 bearer| API[FastAPI]
  API --> RCA[RCA service<br/>engine + challenger]
  API --> ACT[Action service<br/>planner · policy · approvals · executor · validator]
  API --> MCPG[MCP gateway]
  API --> ADP[Project B adapter]
  RCA --> REG[Connector registry]
  ACT --> REG
  REG --> SBX[Sandbox connector<br/>simulated estate]
  REG --> GH[GitHub REST connector]
  MCPG -->|stdio, allow-listed| MCPS[MCP servers]
  ADP --> PB[archai-enterprise-advisor<br/>decision engine]
  API --> DB[(SQLAlchemy<br/>SQLite dev / PostgreSQL)]
  API --> AUD[Hash-chained audit]
```

## Modules (`backend/florome/`)

| Path | Responsibility |
|---|---|
| `models.py` | Persistent domain model: tenants, users, connections, resources, dependencies, incidents, evidence (facts), hypotheses and RCA reports (inferences), plans, approvals, executions, validations, audit, MCP servers/tools, costs |
| `connectors/base.py` | Connector contract and capability declarations |
| `connectors/sandbox.py`, `connectors/github.py` | Implementations |
| `rca/engine.py`, `rca/challenger.py`, `rca/service.py` | Investigation |
| `actions/planner.py`, `actions/service.py` | Remediation lifecycle |
| `governance/policy.py` | Policy-as-code |
| `mcp/gateway.py`, `mcp_servers/` | MCP |
| `security/` | RBAC, audit chain, redaction, injection screening |
| `api/v1.py` | REST API (OpenAPI at `/docs`) |

Design rules:

* Observed facts and inferred conclusions live in separate tables.
* Every tenant-owned row carries `tenant_id`.
* Source identifiers are preserved (`source_system`, `source_ref`).
* No model output is executed.
