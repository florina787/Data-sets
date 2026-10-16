"""Architecture Agent: reproducible Mermaid diagrams.

The patient workflow diagram is rendered directly from the compiled LangGraph, so
it always reflects the code. Other diagrams are generated from the live agent,
tool and MCP registries.
"""

from __future__ import annotations

from app.harness.core import AGENTS, TOOLS


def _safe(s: str) -> str:
    return s.replace('"', "'")


def component_diagram() -> str:
    servers = sorted({t.mcp_server for t in TOOLS.values() if t.mcp_server})
    lines = ["flowchart LR", '  UI["React frontend<br/>Christina copilot"] -->|HTTPS / JWT| API["FastAPI /api/v1"]',
             '  API --> SUP["LangGraph supervisor<br/>patient workflow"]', '  API --> SDLC["LangGraph AI-SDLC workflow"]',
             '  SUP --> H["Agent harness<br/>budgets, allowlists, breakers"]', "  SDLC --> H"]
    for s in servers:
        lines.append(f'  H --> MCP_{s}["MCP: {s}"]')
    lines += ['  H --> RAG["RAG knowledge index"]', '  API --> DB[("PostgreSQL / SQLite")]',
              '  SUP --> CP[("Checkpoint store")]', '  API --> OBS["OpenTelemetry / Prometheus<br/>LangSmith (redacted, opt-in)"]']
    return "\n".join(lines)


def sequence_diagram() -> str:
    return "\n".join([
        "sequenceDiagram", "  actor P as Patient", "  participant C as Christina (UI)", "  participant A as FastAPI",
        "  participant G as LangGraph", "  participant T as Tools (MCP)", "  participant H as Human approval",
        "  P->>C: I need an MRI near Toronto", "  C->>A: POST /copilot/chat", "  A->>G: start workflow",
        "  G->>G: intake, clinical safety, classification", "  G->>T: directory, geo, availability, rules",
        "  T-->>G: typed results (untrusted output sanitised)", "  G->>G: verify, eligibility, wait-time, rank",
        "  G-->>A: recommendations (verified vs unverified)", "  A-->>C: results + DEMO label",
        "  P->>C: Prepare booking handoff", "  C->>A: POST /bookings/request", "  A->>G: booking workflow",
        "  G->>H: interrupt() approval", "  P->>A: POST /approvals/{id}/decision", "  A->>G: resume (Command)",
        "  G-->>C: handoff instructions (NOT_CONFIRMED)"])


def data_flow_diagram() -> str:
    return "\n".join([
        "flowchart TB", '  IN["Patient input"] --> SAFE{"Safety screen"}', '  SAFE -->|urgent| EMG["Emergency guidance"]',
        '  SAFE --> MIN["Data minimisation<br/>(service, coarse location, radius)"]',
        '  MIN --> ST[("Workflow state<br/>no free text")]', '  ST --> AUD[("Hash-chained audit<br/>redacted")]',
        '  ST --> TEL["Telemetry export<br/>redaction before export"]', '  SRC["Availability sources"] -->|untrusted| SAN["Sanitiser"]',
        "  SAN --> ST"])


def agent_diagram() -> str:
    lines = ["flowchart LR"]
    for a in AGENTS.values():
        if a.workflow != "patient":
            continue
        lines.append(f'  {a.name}["{_safe(a.title)}"]')
        for t in sorted(a.allowed_tools):
            lines.append(f'  {a.name} -.-> T_{t.replace(".", "_")}(["{t}"])')
    return "\n".join(lines)


def deployment_diagram() -> str:
    return "\n".join([
        "flowchart LR", '  subgraph Docker Compose', '    FE["frontend (nginx)"] --> BE["backend (uvicorn)"]',
        '    BE --> PG[("postgres:16")]', '    BE --> RD[("redis:7")]', '    PR["prometheus (profile: monitoring)"] --> BE',
        '    GF["grafana (profile: monitoring)"] --> PR', "  end", '  U["Browser"] --> FE'])


def security_boundaries() -> str:
    return "\n".join([
        "flowchart LR", '  subgraph Untrusted', '    B["Browser"]', '    EXT["External sources / MCP output"]', "  end",
        '  subgraph Trusted backend', '    API["API: authn (JWT), RBAC, rate limit, validation"]',
        '    WF["Workflows: tool allowlists, approvals, budgets"]', '    SEC["Secrets: env / secret store only"]', "  end",
        '  subgraph Data', '    DB[("DB: encrypted sensitive fields")]', "  end",
        "  B -->|TLS| API", "  API --> WF", "  EXT -->|sanitised| WF", "  WF --> DB", "  SEC -.-> WF",
        '  WF -->|redacted only| OBS["Observability vendors"]'])


def all_diagrams() -> dict:
    from app.graphs.patient_graph import mermaid
    from app.graphs.sdlc_graph import mermaid as sdlc_mermaid

    return {"patient_workflow": {"title": "Patient workflow (rendered from compiled LangGraph)", "mermaid": mermaid()},
            "sdlc_workflow": {"title": "AI-SDLC workflow (rendered from compiled LangGraph)", "mermaid": sdlc_mermaid()},
            "components": {"title": "High-level component architecture", "mermaid": component_diagram()},
            "sequence": {"title": "Search and booking-handoff sequence", "mermaid": sequence_diagram()},
            "data_flow": {"title": "Data flow and privacy controls", "mermaid": data_flow_diagram()},
            "agents": {"title": "Agent-to-tool permissions (from registry)", "mermaid": agent_diagram()},
            "deployment": {"title": "Local deployment (Docker Compose)", "mermaid": deployment_diagram()},
            "security": {"title": "Security boundaries", "mermaid": security_boundaries()}}
