"""Pattern-specific design detail, produced by the per-pattern graph nodes."""

from __future__ import annotations

from app.models.enums import ArchitectureOption
from app.models.inputs import AssessmentRequest
from app.models.outputs import Decision, PatternDesign

A = ArchitectureOption


def traditional_design(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    keep = decision.primary_architecture is A.KEEP_EXISTING
    return PatternDesign(
        pattern="Keep existing" if keep else "Traditional deterministic software",
        summary=(
            "Retain the existing deterministic system; address pain points with conventional engineering."
            if keep
            else "Implement with deterministic software: rules/workflow engine, APIs and reporting."
        ),
        components=["Existing deterministic system"] if keep else ["Rules / workflow engine", "Service API", "Audit log"],
        design_notes=[
            "Version rules and test them like code (golden test sets, approvals).",
            "If rule-change speed is the pain point, add a governed business-rule authoring UI — not an LLM.",
            "Explicit, exact, reproducible and auditable by construction.",
        ],
    )


def ml_design(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    return PatternDesign(
        pattern="Traditional ML",
        summary="Classical supervised/forecasting model on the existing data platform with human override.",
        components=["Feature pipeline on existing warehouse/lake", "Model training + registry", "Model serving endpoint", "Drift monitoring"],
        design_notes=[
            "Start with an interpretable baseline (e.g. gradient boosting / seasonal models) and compare to current method.",
            "Predictions are advisory; existing systems and people remain accountable.",
            "No LLM is required for prediction/forecasting.",
        ],
    )


def genai_design(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    return PatternDesign(
        pattern="Generative AI",
        summary="Bounded generation/summarization service behind the API gateway; outputs reviewed per policy.",
        components=["AI gateway (model routing, quotas)", "Prompt templates under version control", "Output validation", "Feedback capture"],
        design_notes=["Use structured outputs and response limits.", "Route simple requests to a smaller model."],
    )


def rag_design(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    notes = [
        "Hybrid retrieval: reuse existing keyword search + semantic search; rerank top results.",
        "Permission-aware retrieval: index document ACLs; filter by the requesting user's entitlements.",
        "Answer only from retrieved context; return 'not found' rather than guess.",
    ]
    if decision.citations_mandatory:
        notes.append("Citations are mandatory: each claim links to a source document and passage.")
    if decision.human_review_mandatory:
        notes.append("All generated output is a draft until reviewed by a qualified human.")
    return PatternDesign(
        pattern="RAG + Generative AI",
        summary="Retrieval service grounded in governed enterprise documents, deployed on the existing platform.",
        components=["Ingestion pipeline (governed sources)", "Chunking + metadata/ACL indexing", "Vector index (only because semantic retrieval is justified)", "Retriever + reranker", "Grounded generation with citations"],
        design_notes=notes,
    )


def agentic_design(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    tools = [f"read: {s}" for s in req.current_architecture.existing_systems[:5]]
    return PatternDesign(
        pattern="Constrained Agentic AI",
        summary="LangGraph orchestrator that uses existing service APIs as allow-listed tools; humans approve every write.",
        components=["LangGraph orchestrator (state machine, max iterations)", "Tool adapters over existing APIs", "Approval service / existing ITSM change workflow", "Agent audit trail"] + tools,
        design_notes=[
            "Read-only investigation tools are enabled by default; write tools only propose actions.",
            "Agents call existing APIs — they never replace existing microservices or bypass the API gateway.",
            "Bounded by iteration limit, token budget and timeout; partial results are returned on breach.",
            "Deterministic steps stay deterministic (workflow edges), the LLM is used only where reasoning is needed.",
        ],
    )


def design_for(req: AssessmentRequest, decision: Decision) -> PatternDesign:
    patterns = decision.ai_patterns
    if not patterns:
        return traditional_design(req, decision)
    return {
        A.AGENTIC_AI: agentic_design,
        A.RAG_GENAI: rag_design,
        A.GENERATIVE_AI: genai_design,
        A.TRADITIONAL_ML: ml_design,
    }[patterns[0]](req, decision)
