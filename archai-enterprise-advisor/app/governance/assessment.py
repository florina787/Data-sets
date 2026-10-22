"""Security & governance assessment (industry-aware)."""

from __future__ import annotations

from app.models.enums import (
    DETERMINISTIC_ONLY_ACTIONS,
    HIGH_RISK_WRITE_ACTIONS,
    LOW_RISK_WRITE_ACTIONS,
    REGULATED_INDUSTRIES,
    ActionType,
    ArchitectureOption,
    IdentitySecurity,
    Industry,
)
from app.models.inputs import AssessmentRequest
from app.models.outputs import Control, Decision, ScoreCard, SecurityAssessment, Threat
from app.security.agent_guardrails import default_guardrails

A = ArchitectureOption

INDUSTRY_CONSIDERATIONS: dict[Industry, list[str]] = {
    Industry.BANKING: [
        "PII and financial data protection; transaction integrity",
        "Regulatory obligations, auditability and explainability of every decision",
        "Model risk management (independent validation, inventory, monitoring)",
        "Segregation of duties and human approval for material actions",
        "Data residency, business continuity and third-party (model provider) risk",
        "Never delegate money movement, payment authorization, regulatory calculations, authentication, authorization or compliance rules to autonomous agents",
    ],
    Industry.FINANCIAL_SERVICES: [
        "PII/financial data protection and data residency",
        "Model risk management and third-party model risk",
        "Auditability, explainability and change management for production actions",
        "Segregation of duties; human approval for remediation and material actions",
        "Business continuity — AI must degrade gracefully",
    ],
    Industry.LEGAL: [
        "Client confidentiality and attorney-client privilege",
        "Matter-level access control / ethical walls",
        "Document provenance and mandatory source citations",
        "Hallucination consequences (sanctions, malpractice) — mandatory lawyer review",
        "Retention requirements, jurisdiction and data residency",
    ],
    Industry.RETAIL: [
        "Customer PII and consent for personalization",
        "Latency and cost at seasonal peak volume",
        "Brand risk from customer-facing generated content",
        "Order/inventory facts must come from systems of record",
    ],
    Industry.GENERAL_ENTERPRISE: [
        "Data classification and least-privilege access",
        "Acceptable-use policy and vendor data-processing terms",
        "Proportionate controls for low-risk internal workloads",
    ],
}


def _classification(req: AssessmentRequest) -> str:
    dp = req.data_profile
    if dp.privileged:
        return "RESTRICTED — legally privileged"
    if dp.contains_financial_data or (dp.contains_pii and req.organization.industry in REGULATED_INDUSTRIES):
        return "RESTRICTED — regulated personal/financial data"
    if dp.confidential or dp.contains_pii:
        return "CONFIDENTIAL"
    return "INTERNAL"


def _tools_for(req: AssessmentRequest) -> tuple[list[str], list[str]]:
    reads = ["search_knowledge_base"] if req.use_case.proprietary_knowledge_need >= 2 else []
    reads += [f"read_{s.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('&', 'and')}" for s in req.current_architecture.existing_systems[:5]]
    writes = []
    for action in req.use_case.action_types:
        if action in HIGH_RISK_WRITE_ACTIONS | LOW_RISK_WRITE_ACTIONS:
            writes.append(f"propose_{action.value}")
    return reads, writes


def agent_threats(req: AssessmentRequest, decision: Decision) -> list[Threat]:
    patterns = set(decision.ai_patterns)
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    rag = A.RAG_GENAI in patterns or (A.AGENTIC_AI in patterns and req.use_case.proprietary_knowledge_need >= 2)
    agent = A.AGENTIC_AI in patterns
    multi_user = True
    sensitive = req.data_profile.confidential or req.data_profile.contains_pii or req.data_profile.privileged
    high = "HIGH" if sensitive else "MEDIUM"

    def t(name: str, applies: bool, likelihood: str, impact: str, mitigations: list[str]) -> Threat:
        return Threat(name=name, applies=applies, likelihood=likelihood if applies else "N/A", impact=impact if applies else "N/A", mitigations=mitigations)

    return [
        t("Direct prompt injection", llm, "HIGH", high, ["Input validation", "System-prompt isolation", "Output policy checks", "Never grant authority via prompt text"]),
        t("Indirect prompt injection (via documents/tool output)", rag or agent, "MEDIUM", high, ["Screen retrieved content", "Treat retrieved text as data, never instructions", "Content provenance"]),
        t("Excessive agency", agent, "MEDIUM", "HIGH", ["Tool allow-list", "Least-privilege service identities", "Human approval for writes"]),
        t("Unauthorized tool execution", agent, "MEDIUM", "HIGH", ["Allow-list enforcement", "Per-user authorization propagated to tools", "Audit log"]),
        t("Hallucinated tool parameters", agent, "MEDIUM", "MEDIUM", ["Pydantic schema validation", "Reject-and-retry with limit", "Dry-run for writes"]),
        t("Infinite loops / runaway iterations", agent, "MEDIUM", "MEDIUM", ["Max iterations", "Wall-clock timeout", "Loop detection"]),
        t("Runaway token usage", llm, "MEDIUM", "MEDIUM", ["Per-request token budget", "Response-length caps", "Cost alerts"]),
        t("Poisoned RAG content", rag, "LOW", high, ["Ingestion from governed sources only", "Content owner approval", "Integrity checks"]),
        t("Data exfiltration", llm, "LOW", high, ["Egress controls", "No arbitrary URL tools", "DLP on outputs"]),
        t("Cross-user data leakage", llm and multi_user, "MEDIUM", high, ["Permission-aware retrieval", "Per-user context isolation", "No shared conversation memory"]),
        t("Privilege escalation", agent, "LOW", "HIGH", ["Agent identity ≤ user's entitlements", "No admin scopes", "Segregation of duties"]),
        t("Malicious documents", rag, "LOW", "MEDIUM", ["Malware scanning at ingestion", "File-type allow-list", "Sandboxed parsing"]),
        t("Tool failure / partial failure", agent, "MEDIUM", "MEDIUM", ["Timeouts", "Retries with backoff", "Circuit breakers", "Idempotent writes"]),
    ]


def assess_security(req: AssessmentRequest, decision: Decision, scores: ScoreCard) -> SecurityAssessment:
    org, dp, uc = req.organization, req.data_profile, req.use_case
    ids = set(req.current_architecture.identity_security)
    patterns = set(decision.ai_patterns)
    ai = bool(patterns)
    agent = A.AGENTIC_AI in patterns
    llm = bool(patterns & {A.GENERATIVE_AI, A.RAG_GENAI, A.AGENTIC_AI})
    regulated = org.industry in REGULATED_INDUSTRIES
    controls: list[Control] = []

    def c(category: str, control: str, priority: str, reason: str = "") -> None:
        controls.append(Control(category=category, control=control, priority=priority, reason=reason))

    if not ai:
        c("Architecture", "Keep deterministic processing in existing, audited systems", "MUST", "No AI component recommended.")
        c("Governance", "Record this decision in an ADR and re-assess only if requirements change", "SHOULD")
        if set(uc.action_types) & DETERMINISTIC_ONLY_ACTIONS:
            c("Change management", "Improve rule-change agility with rule versioning, testing and a business-rule UI instead of AI", "SHOULD", "Addresses the original pain point deterministically.")
    else:
        c("Identity", "Propagate end-user identity (OIDC/OAuth 2.0) to every AI request and tool call", "MUST")
        c("Authorization", "Enforce RBAC/ABAC on retrieval and tools — AI never exceeds the user's entitlements", "MUST")
        c("Least privilege", "Dedicated, minimally scoped service accounts for AI components", "MUST")
        c("Secrets", "Model/API credentials only in a secrets manager; never in code, prompts, logs or frontends", "MUST",
          "" if IdentitySecurity.SECRETS_MANAGEMENT in ids else "Gap: no secrets manager in current state.")
        c("Network", "Route AI traffic through the existing API Gateway and private networking", "MUST" if regulated else "SHOULD")
        c("Audit", "Immutable audit log: prompt, retrieved sources, tool calls, outputs, approver, decision", "MUST")
        if llm:
            c("Prompt security", "Prompt-injection defenses: input screening, instruction hierarchy, output validation", "MUST")
            c("Data leakage", "DLP/PII redaction on prompts and outputs; no training on enterprise data by providers", "MUST" if dp.contains_pii or dp.confidential else "SHOULD")
            c("Model access", "Approved model catalogue with an AI gateway enforcing quotas and model allow-list", "SHOULD")
        if A.RAG_GENAI in patterns or (agent and uc.proprietary_knowledge_need >= 2):
            c("Retrieval", "Permission-aware retrieval (document ACLs indexed with chunks; filtered at query time)", "MUST")
            c("Content integrity", "Ingest only from governed sources; screen retrieved content for injected instructions", "MUST")
        if decision.citations_mandatory:
            c("Provenance", "Every generated claim cites a retrievable source; unanswerable → explicit 'not found'", "MUST")
        if agent:
            c("Tool governance", "Tool allow-list; read tools default; write tools require approval", "MUST")
            c("Validation", "Schema-validate every tool parameter; reject hallucinated arguments", "MUST")
            c("Runaway control", "Max iterations, token budget and timeout per agent run", "MUST")
            c("Sandboxing", "Execute tools in sandboxed, idempotent adapters around existing APIs", "SHOULD")
        if decision.requires_human_approval:
            c("Human-in-the-loop", "Named approver with segregation of duties for every high-risk action", "MUST")
        if dp.data_residency_required:
            c("Residency", "Keep data and inference in approved regions/on-prem; verify provider processing locations", "MUST")
        if regulated:
            c("Model risk", "Register the AI system in the model inventory; independent validation before production", "MUST")
        if dp.privileged:
            c("Privilege", "Matter-level ethical walls enforced in the index; no cross-matter retrieval", "MUST")

    reads, writes = _tools_for(req)
    guard = default_guardrails(agentic=agent, regulated=regulated, write_tools=writes if agent else [], read_tools=reads)

    governance = [
        f"Autonomy ceiling: {decision.autonomy_label}",
        "AI system owner, data owner and risk owner named before pilot",
        "Evaluation gates (see Evaluation) must pass before each roadmap phase",
        "Incident response playbook covers AI-specific failures (hallucination, injection, leakage)",
    ]
    if regulated:
        governance.append("Model risk management review and sign-off")
    if decision.human_review_mandatory:
        governance.append("100% human review of AI output is mandatory")
    if set(uc.action_types) & {ActionType.PRODUCTION_REMEDIATION}:
        governance.append("Production remediation only through existing change management with human approval")

    return SecurityAssessment(
        security_risk_score=scores.security_risk.value,
        data_classification=_classification(req),
        controls=controls,
        agent_threats=agent_threats(req, decision) if ai else [],
        governance_requirements=governance,
        industry_considerations=INDUSTRY_CONSIDERATIONS[org.industry],
        agent_guardrail_config=guard.as_dict() if ai else {},
    )
