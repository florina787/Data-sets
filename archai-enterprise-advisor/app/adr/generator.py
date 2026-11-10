"""Architecture Decision Record generation (Markdown)."""

from __future__ import annotations

from datetime import date

from app.architecture.diagrams import ascii_target
from app.architecture.matrix import pretty
from app.models.inputs import AssessmentRequest
from app.models.outputs import (
    ADR,
    BuildVsBuyAssessment,
    ChallengerResult,
    CostBreakdown,
    Decision,
    DiscoveryResult,
    EvaluationPlan,
    MatrixRow,
    ModelDeploymentStrategy,
    Roadmap,
    ROIResult,
    ScoreCard,
    SecurityAssessment,
)


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- None"


def build_adr(
    req: AssessmentRequest,
    *,
    discovery: DiscoveryResult,
    decision: Decision,
    scores: ScoreCard,
    security: SecurityAssessment,
    cost: CostBreakdown,
    roi: ROIResult,
    matrix: list[MatrixRow],
    challenger: ChallengerResult,
    roadmap: Roadmap,
    evaluation: EvaluationPlan,
    build_vs_buy: BuildVsBuyAssessment,
    model_deployment: ModelDeploymentStrategy,
    request_id: str = "",
) -> ADR:
    arch = req.current_architecture
    title = f"ADR: {decision.architecture_label} for '{req.use_case.title}'"
    current = (
        f"- Deployment: {', '.join(pretty(d) for d in arch.deployment) or 'n/a'}\n"
        f"- Compute: {', '.join(pretty(c) for c in arch.compute) or 'n/a'}\n"
        f"- Architecture: {', '.join(pretty(s) for s in arch.styles) or 'n/a'}\n"
        f"- Integration: {', '.join(pretty(i) for i in arch.integration) or 'n/a'}\n"
        f"- Identity & security: {', '.join(pretty(i) for i in arch.identity_security) or 'n/a'}\n"
        f"- Data: {', '.join(pretty(d) for d in arch.data_stores) or 'n/a'}\n"
        f"- DevOps/observability: {', '.join(pretty(d) for d in arch.devops) or 'n/a'}\n"
        f"- Existing systems: {', '.join(arch.existing_systems) or 'n/a'}"
    )
    score_rows = "\n".join(
        f"| {getattr(scores, k).label} | {getattr(scores, k).value:.0f} | {getattr(scores, k).band} |" for k in type(scores).model_fields
    )
    matrix_rows = "\n".join(f"| {r.component} | {r.decision.value} | {r.reason} |" for r in matrix)
    rejected = "\n".join(f"- **{r.option.value}** — {r.reason}" for r in decision.rejected_alternatives)
    must_controls = [f"{c.category}: {c.control}" for c in security.controls if c.priority == "MUST"]
    risks = [f"{t.name} (likelihood {t.likelihood}, impact {t.impact})" for t in security.agent_threats if t.applies]
    phases = "\n".join(
        f"- **Phase {p.phase} — {p.name}**{'' if p.included else ' (not planned)'}: {p.objective} _Autonomy ceiling: L{int(p.autonomy_ceiling)}._"
        for p in roadmap.phases
    )
    metrics = "\n".join(f"| {m.name} | {m.target} |" for m in evaluation.metrics)
    challenge = "\n".join(f"- {c.verdict.value} — {c.question} {c.finding}" for c in challenger.questions)
    reassess = [
        "Business requirements, volumes or risk appetite change materially",
        "Measured KPIs miss acceptance criteria for two consecutive review periods",
        "Regulatory guidance on AI use in this domain changes",
        "Model pricing or capability changes alter the cost/ROI conclusion",
        "Security incident or guardrail breach involving the AI component",
    ]
    if not decision.ai_recommended:
        reassess.insert(0, "The workload gains material prediction, generation, knowledge or variable-workflow needs")

    md = f"""# {title}

- **Status:** Proposed
- **Date:** {date.today().isoformat()}
- **Organization:** {req.organization.name} ({req.organization.industry.value})
- **Assessment ID:** {request_id or 'n/a'}
- **Decision engine:** deterministic rules + weighted scoring (no LLM in the decision path)

## Business problem
{discovery.business_problem}

- Users: {discovery.users}
- Desired outcome: {discovery.desired_outcome}
- Current solution: {discovery.current_solution}

## Current architecture
{current}

## Constraints
{_bullets(discovery.constraints)}

## Assumptions
{_bullets(discovery.assumptions)}

## Scores
| Score | Value | Band |
|---|---|---|
{score_rows}

## Alternatives considered
Keep existing · Traditional software · Traditional ML · Generative AI · RAG + GenAI · Agentic AI · Hybrid

## Decision
**{decision.primary_architecture_label}: {decision.architecture_label}**

- AI verdict: **{decision.ai_verdict_label}**
- Agentic AI: **{decision.agentic_verdict_label}** — {decision.agentic_answer}
- Autonomy: **{decision.autonomy_label}**
- Human approval required: **{'Yes' if decision.requires_human_approval else 'No'}** · Human review mandatory: **{'Yes' if decision.human_review_mandatory else 'No'}** · Citations mandatory: **{'Yes' if decision.citations_mandatory else 'No'}**
- Authoritative systems: {', '.join(decision.authoritative_systems) or 'n/a'}
- Build vs buy: **{build_vs_buy.decision.value}** — {build_vs_buy.summary}
- Model deployment: {model_deployment.recommended}

### Reasons
{_bullets(decision.rationale + decision.agentic_rationale)}

### Rules triggered
{_bullets(decision.triggered_rules)}

## Rejected alternatives
{rejected or '- None'}

## Transformation matrix
| Component | Decision | Reason |
|---|---|---|
{matrix_rows}

## Target architecture
```
{ascii_target(req, decision)}
```

## Security implications
- Data classification: {security.data_classification}
{_bullets(must_controls)}

## Cost implications (sample pricing — illustrative)
- Proposed monthly run cost: ${cost.proposed_cost_month:,.0f} (current ${cost.current_cost_month:,.0f})
- Model cost/month: ${cost.model_cost_month:,.0f}; optimization savings vs unoptimized: ${cost.optimization_savings_month:,.0f}
- ROI verdict: **{roi.verdict.value}** — net annual benefit ${roi.net_annual_benefit:,.0f}; payback {roi.payback_months if roi.payback_months is not None else 'n/a'} months

## Risks
{_bullets(risks) if risks else '- No AI-specific risks introduced (no AI component).'}

## Challenger review
{challenge}

## Migration approach
{phases}

## Evaluation criteria
| Metric | Target |
|---|---|
{metrics}

_{evaluation.disclaimer}_

## Conditions requiring reassessment
{_bullets(reassess)}

---
_Generated by ArchAI. All companies and data in the ArchAI repository are fictional/synthetic._
"""
    return ADR(title=title, status="Proposed", markdown=md)
