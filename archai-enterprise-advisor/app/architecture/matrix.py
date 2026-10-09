"""KEEP / ENHANCE / ADD / REPLACE transformation matrix.

REPLACE is only ever produced for components the organization has itself
flagged as end-of-life — never because "AI could do it".
"""

from __future__ import annotations

from app.models.enums import (
    CI_CD_TOOLS,
    OBSERVABILITY_TOOLS,
    ArchitectureOption,
    ArchitectureStyle,
    Compute,
    DataStore,
    IdentitySecurity,
    Integration,
    MatrixDecision,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, MatrixRow

A = ArchitectureOption
K, E, ADD, NA, R = MatrixDecision.KEEP, MatrixDecision.ENHANCE, MatrixDecision.ADD, MatrixDecision.NOT_ADDED, MatrixDecision.REPLACE

_PRETTY = {
    Compute.KUBERNETES: "Kubernetes", Compute.OPENSHIFT: "OpenShift", Compute.DOCKER: "Docker",
    Compute.VIRTUAL_MACHINES: "Virtual Machines", Compute.BARE_METAL: "Bare Metal", Compute.SERVERLESS: "Serverless",
    DataStore.POSTGRESQL: "PostgreSQL", DataStore.ORACLE: "Oracle", DataStore.SQL_SERVER: "SQL Server", DataStore.MYSQL: "MySQL",
    DataStore.MONGODB: "MongoDB", DataStore.DATA_LAKE: "Data Lake", DataStore.DATA_WAREHOUSE: "Data Warehouse",
    DataStore.OBJECT_STORAGE: "Object Storage", DataStore.SHAREPOINT: "SharePoint", DataStore.DOCUMENT_REPOSITORY: "Document Repository",
    DataStore.VECTOR_DATABASE: "Vector Database", DataStore.SEARCH_ENGINE: "Search Engine",
}


def pretty(value: object) -> str:
    if value in _PRETTY:
        return _PRETTY[value]  # type: ignore[index]
    return str(getattr(value, "value", value)).replace("_", " ").title()


def build_matrix(req: AssessmentRequest, decision: Decision) -> list[MatrixRow]:
    arch, uc = req.current_architecture, req.use_case
    patterns = set(decision.ai_patterns)
    ai = bool(patterns)
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    rag = A.RAG_GENAI in patterns or (A.AGENTIC_AI in patterns and uc.proprietary_knowledge_need >= 3)
    agent = A.AGENTIC_AI in patterns
    eol = {c.lower() for c in arch.end_of_life_components}
    rows: list[MatrixRow] = []

    def row(component: str, decision_: MatrixDecision, reason: str) -> None:
        if component.lower() in eol:
            rows.append(MatrixRow(component=component, decision=R, reason="Flagged end-of-life by the organization — replace with a supported equivalent (not with AI by default)."))
        else:
            rows.append(MatrixRow(component=component, decision=decision_, reason=reason))

    for d in arch.deployment:
        row(f"Deployment: {pretty(d)}", K, "AI fits into the existing hosting model; no migration required for AI.")
    for c in arch.compute:
        if c in (Compute.KUBERNETES, Compute.OPENSHIFT):
            row(pretty(c), K, "Existing scalable platform — AI services deploy as ordinary workloads." if ai else "Existing scalable platform.")
        else:
            row(pretty(c), K, "Existing compute retained.")
    for s in arch.styles:
        if s is ArchitectureStyle.MICROSERVICES:
            row("Microservices", K, "Existing business logic remains authoritative; AI calls their APIs." if ai else "Existing business logic remains authoritative.")
        elif s is ArchitectureStyle.MONOLITH:
            row("Monolith", K, "Integrate via an adapter API at the edge; do not modify core logic for AI.")
        else:
            row(pretty(s) + " architecture", K, "Retained.")
    ids = set(arch.identity_security)
    if IdentitySecurity.API_GATEWAY in ids:
        row("API Gateway", K, "Existing security boundary; add AI route policies and quotas." if ai else "Existing security boundary.")
    elif ai:
        row("API Gateway", ADD, "Required governed entry point for AI endpoints.")
    id_names = [pretty(i) for i in ids & {IdentitySecurity.ACTIVE_DIRECTORY, IdentitySecurity.ENTRA_ID, IdentitySecurity.OIDC, IdentitySecurity.OAUTH2}]
    if id_names:
        row("Identity (" + ", ".join(sorted(id_names)) + ")", K, "Propagate end-user identity into AI requests and tools." if ai else "Retained.")
    if ai and IdentitySecurity.SECRETS_MANAGEMENT not in ids:
        row("Secrets Management", ADD, "Required for model/API credentials.")
    for system in arch.existing_systems:
        if uc.replaces_existing_component and system.lower() == uc.replaces_existing_component.lower():
            row(system, K, "Replacement with AI rejected — deterministic, auditable and fit for purpose." if not ai else "Retained; AI augments rather than replaces it.")
        elif "rule" in system.lower():
            row(system, K, "Deterministic processing remains authoritative.")
        elif rag and any(k in system.lower() for k in ("document", "sharepoint", "library", "repository", "faq", "runbook")):
            row(system, E, "Source of record for retrieval; ingest content with permissions metadata.")
        else:
            row(system, K, "System of record — remains authoritative; exposed to AI only through governed APIs." if ai else "Retained.")
    for ds in arch.data_stores:
        name = pretty(ds)
        if ds is DataStore.VECTOR_DATABASE:
            row(name, K, "Reused for semantic retrieval (justified by use case)." if rag else "Exists but not used — semantic retrieval is not justified for this use case.")
        elif ds is DataStore.SEARCH_ENGINE:
            row(name, E if rag else K, "Hybrid retrieval (keyword + semantic) and fallback when vector search is unavailable." if rag else "Retained.")
        elif ds in (DataStore.SHAREPOINT, DataStore.DOCUMENT_REPOSITORY):
            row(name, E if rag else K, "Governed document source; index content with ACLs." if rag else "Retained.")
        elif ds in (DataStore.DATA_WAREHOUSE, DataStore.DATA_LAKE) and A.TRADITIONAL_ML in patterns:
            row(name, E, "Feature source for ML training and scoring.")
        else:
            row(name, K, "System of record — unchanged.")
    if Integration.KAFKA in arch.integration:
        row("Kafka", K, "Event backbone; can trigger AI workflows asynchronously." if agent else "Retained.")
    if set(arch.devops) & CI_CD_TOOLS:
        row("CI/CD (" + ", ".join(pretty(t) for t in sorted(set(arch.devops) & CI_CD_TOOLS, key=lambda t: t.value)) + ")",
            E if ai else K, "Add evaluation gates and prompt/config versioning." if ai else "Retained.")
    if set(arch.devops) & OBSERVABILITY_TOOLS:
        row("Monitoring (" + ", ".join(pretty(t) for t in sorted(set(arch.devops) & OBSERVABILITY_TOOLS, key=lambda t: t.value)) + ")",
            E if ai else K, "Add AI telemetry: tokens, cost, latency, groundedness, tool calls, overrides." if ai else "Retained.")

    # New components — added only when justified.
    if DataStore.VECTOR_DATABASE not in arch.data_stores:
        if rag:
            rows.append(MatrixRow(component="Vector Store", decision=ADD, reason="Semantic retrieval is justified by proprietary-knowledge and citation needs."))
        else:
            rows.append(MatrixRow(component="Vector Store", decision=NA, reason="Semantic retrieval not justified."))
    rows.append(MatrixRow(component="RAG Service", decision=ADD if rag else NA, reason="Grounded answers with citations." if rag else "No document-grounding need."))
    rows.append(MatrixRow(component="LangGraph AI Orchestrator", decision=ADD if agent else NA,
                          reason="Agent orchestration justified for variable cross-system workflow; wraps existing APIs." if agent else "Agent orchestration not justified."))
    rows.append(MatrixRow(component="AI Gateway / Model Access", decision=ADD if llm else NA,
                          reason="Model routing, quotas, logging and provider abstraction." if llm else "No LLM required."))
    if A.TRADITIONAL_ML in patterns:
        rows.append(MatrixRow(component="ML Training & Serving", decision=ADD, reason="Model registry, serving and drift monitoring on the existing platform."))
    if ai:
        rows.append(MatrixRow(component="AI Evaluation Harness", decision=ADD, reason="Acceptance criteria gate every roadmap phase."))
    if ai and decision.requires_human_approval:
        rows.append(MatrixRow(component="Human Approval Workflow", decision=ADD if agent else E,
                              reason="Approval gate for high-risk actions with audit trail." if agent else "Review step for AI-drafted output."))
    return rows
