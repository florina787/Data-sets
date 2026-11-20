"""Mermaid diagram generation for current- and target-state architectures."""

from __future__ import annotations

import re

from app.architecture.matrix import pretty
from app.models.enums import (
    OBSERVABILITY_TOOLS,
    ArchitectureOption,
    ArchitectureStyle,
    DataStore,
    IdentitySecurity,
    Integration,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision

A = ArchitectureOption
_RECORD = {DataStore.ORACLE, DataStore.POSTGRESQL, DataStore.SQL_SERVER, DataStore.MYSQL, DataStore.MONGODB}
_DOCS = {DataStore.SHAREPOINT, DataStore.DOCUMENT_REPOSITORY, DataStore.SEARCH_ENGINE, DataStore.VECTOR_DATABASE}


def _label(text: str) -> str:
    """Escape text for a Mermaid quoted label."""
    return re.sub(r'["<>]', "", text).replace("&", "and")


class _Diagram:
    def __init__(self) -> None:
        self.lines: list[str] = ["flowchart TD"]

    def add(self, line: str) -> None:
        self.lines.append("    " + line)

    def render(self) -> str:
        return "\n".join(self.lines)


def _platform_lines(d: _Diagram, req: AssessmentRequest, *, kept_class: bool) -> dict[str, str]:
    """Emit the existing environment; return ids of key nodes."""
    arch = req.current_architecture
    env = " + ".join(pretty(x) for x in arch.deployment) or "Existing Environment"
    compute = " / ".join(pretty(c) for c in arch.compute) or "Compute"
    if ArchitectureStyle.MICROSERVICES in arch.styles:
        services = "Existing Microservices"
    elif ArchitectureStyle.MONOLITH in arch.styles:
        services = "Existing Core Application"
    else:
        services = "Existing Services (" + ", ".join(pretty(s) for s in arch.styles) + ")" if arch.styles else "Existing Services"
    ids: dict[str, str] = {}
    d.add('USERS(["Business Users"])')
    d.add(f'subgraph ENV["{_label(("Existing Environment: " if kept_class else "") + env)}"]')
    d.add("direction TB")
    d.add(f'PLAT["{_label(compute)}"]')
    if IdentitySecurity.API_GATEWAY in arch.identity_security:
        d.add('GW["API Gateway"]')
        ids["gw"] = "GW"
    d.add(f'SVC["{_label(services)}"]')
    for i, system in enumerate(arch.existing_systems[:5]):
        d.add(f'SYS{i}["{_label(system)}"]')
    for i, ds in enumerate(sorted(set(arch.data_stores) & _RECORD, key=lambda x: x.value)):
        d.add(f'DB{i}[("{_label(pretty(ds))}")]')
    for i, ds in enumerate(sorted(set(arch.data_stores) & _DOCS, key=lambda x: x.value)):
        d.add(f'DOC{i}[("{_label(pretty(ds))}")]')
    if Integration.KAFKA in arch.integration:
        d.add('KAFKA[["Kafka"]]')
    obs = sorted(set(arch.devops) & OBSERVABILITY_TOOLS, key=lambda x: x.value)
    if obs:
        d.add(f'OBS["Monitoring: {_label(", ".join(pretty(o) for o in obs))}"]')
    d.add("end")

    entry = ids.get("gw", "SVC")
    d.add(f"USERS --> {entry}")
    if entry != "SVC":
        d.add(f"{entry} --> SVC")
    d.add("PLAT -.- SVC")
    for i, _ in enumerate(arch.existing_systems[:5]):
        d.add(f"SVC --> SYS{i}")
    for i, _ in enumerate(sorted(set(arch.data_stores) & _RECORD, key=lambda x: x.value)):
        d.add(f"SVC --> DB{i}")
    for i, _ in enumerate(sorted(set(arch.data_stores) & _DOCS, key=lambda x: x.value)):
        d.add(f"SVC -.-> DOC{i}")
    if Integration.KAFKA in arch.integration:
        d.add("SVC <--> KAFKA")
    ids["entry"] = entry
    ids["has_obs"] = "yes" if obs else ""
    return ids


def current_state_mermaid(req: AssessmentRequest) -> str:
    d = _Diagram()
    _platform_lines(d, req, kept_class=False)
    d.add("classDef existing fill:#eef2f7,stroke:#64748b,color:#0f172a")
    d.add("class PLAT,SVC existing")
    return d.render()


def target_state_mermaid(req: AssessmentRequest, decision: Decision) -> str:
    d = _Diagram()
    ids = _platform_lines(d, req, kept_class=True)
    patterns = set(decision.ai_patterns)
    entry = ids["entry"]
    added: list[str] = []
    if not patterns:
        d.add('NOAI["No AI component added: existing deterministic systems remain authoritative"]')
        d.add("SVC --- NOAI")
        d.add("classDef existing fill:#eef2f7,stroke:#64748b,color:#0f172a")
        d.add("classDef note fill:#fff7ed,stroke:#ea580c,color:#7c2d12")
        d.add("class PLAT,SVC existing")
        d.add("class NOAI note")
        return d.render()

    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    rag = A.RAG_GENAI in patterns
    agent = A.AGENTIC_AI in patterns
    d.add('subgraph AI["AI capability layer (added on existing platform)"]')
    d.add("direction TB")
    if agent:
        d.add('ORCH["AI Orchestrator (LangGraph): allow-listed tools, max iterations"]')
        added.append("ORCH")
    if rag:
        d.add('RAG["RAG Service: permission-aware retrieval + citations"]')
        has_vdb = DataStore.VECTOR_DATABASE in req.current_architecture.data_stores
        d.add('VEC[("Vector Store (existing, reused)")]' if has_vdb else 'VEC[("Vector Store")]')
        d.add("RAG --> VEC")
        added += ["RAG"] + ([] if has_vdb else ["VEC"])
    if llm and not rag and not agent:
        d.add('GENAI["GenAI Service: bounded generation"]')
        added.append("GENAI")
    if llm:
        d.add('AIGW["AI Gateway: routing, quotas, audit"]')
        d.add('LLM["LLM (per deployment strategy)"]')
        d.add("AIGW --> LLM")
        added += ["AIGW", "LLM"]
    if A.TRADITIONAL_ML in patterns:
        d.add('ML["ML Model Serving + Drift Monitoring"]')
        added.append("ML")
    d.add('EVAL["Evaluation + AI Telemetry"]')
    added.append("EVAL")
    d.add("end")

    if agent:
        d.add(f"{entry} --> ORCH")
        d.add(f'ORCH -- "tools = existing APIs" --> {entry}')
        if rag:
            d.add("ORCH --> RAG")
        d.add("ORCH --> AIGW")
    if rag and not agent:
        d.add(f"{entry} --> RAG")
        d.add("RAG --> AIGW")
    if "GENAI" in added:
        d.add(f"{entry} --> GENAI")
        d.add("GENAI --> AIGW")
    if rag:
        for i, _ in enumerate(sorted(set(req.current_architecture.data_stores) & _DOCS, key=lambda x: x.value)):
            d.add(f'DOC{i} -. "governed ingestion" .-> RAG')
    if A.TRADITIONAL_ML in patterns:
        d.add('SVC -- "scoring API" --> ML')
    if decision.requires_human_approval or decision.human_review_mandatory:
        label = "Human Approval (named approver, audit)" if decision.requires_human_approval and agent else "Human Review of AI output"
        d.add(f'HUMAN{{"{label}"}}')
        added.append("HUMAN")
        if agent:
            d.add('ORCH -- "proposed write" --> HUMAN')
            d.add(f'HUMAN -- "approved" --> {entry}')
        else:
            src = "RAG" if rag else ("GENAI" if "GENAI" in added else "ML")
            d.add(f"{src} --> HUMAN")
            d.add("HUMAN --> USERS")
    if ids.get("has_obs"):
        d.add("EVAL -.-> OBS")
    d.add("classDef existing fill:#eef2f7,stroke:#64748b,color:#0f172a")
    d.add("classDef added fill:#dcfce7,stroke:#16a34a,color:#14532d")
    d.add("class PLAT,SVC existing")
    d.add("class " + ",".join(added) + " added")
    return d.render()


def ascii_target(req: AssessmentRequest, decision: Decision) -> str:
    """Plain-text target diagram (used in ADRs and terminal output)."""
    compute = " / ".join(pretty(c) for c in req.current_architecture.compute) or "Platform"
    lines = ["Existing Environment", "        |", f"   {compute}", "        |", " Existing Services / Microservices", "        |", "    API Gateway"]
    patterns = set(decision.ai_patterns)
    if not patterns:
        lines += ["        |", " (no AI added — existing systems remain authoritative)"]
        return "\n".join(lines)
    left = "RAG Service" if A.RAG_GENAI in patterns else ("ML Serving" if A.TRADITIONAL_ML in patterns else "GenAI Service")
    right = "AI Orchestrator (LangGraph)" if A.AGENTIC_AI in patterns else "AI Gateway"
    lines += ["        |", "  -----------------------", "  |                     |", f"{left:<22}{right}", "  |                     |", "  ------- APIs ----------", "        |", " Existing Systems (authoritative)"]
    if decision.requires_human_approval or decision.human_review_mandatory:
        lines += ["        |", " Human Approval / Review"]
    return "\n".join(lines)
