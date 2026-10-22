"""Architecture generator, roadmap, ADR, build-vs-buy and observability."""

from __future__ import annotations

from app.models.enums import AutonomyLevel, MatrixDecision, SourcingDecision


def test_target_diagram_adds_ai_around_existing_apis(assess):
    r = assess("finops-incident-investigation")
    target = r.target_architecture.target_state_mermaid
    assert target.startswith("flowchart TD")
    assert "LangGraph" in target and "Human Approval" in target and "Existing Microservices" in target
    assert "existing APIs" in target
    assert "LangGraph AI Orchestrator" in r.target_architecture.added_components


def test_no_ai_target_diagram_adds_nothing(assess):
    r = assess("banking-transaction-rules")
    assert "No AI component added" in r.target_architecture.target_state_mermaid
    assert not [m for m in r.matrix if m.decision is MatrixDecision.ADD]


def test_roadmap_never_jumps_to_unrestricted_autonomy(assess):
    for sid in ["finops-incident-investigation", "legal-research", "banking-policy-knowledge"]:
        r = assess(sid)
        phases = r.roadmap.phases
        assert [p.phase for p in phases] == [0, 1, 2, 3, 4, 5]
        assert all(p.autonomy_ceiling < AutonomyLevel.AUTONOMOUS for p in phases)
        assert phases[1].autonomy_ceiling <= AutonomyLevel.READ_ONLY
        ceilings = [p.autonomy_ceiling for p in phases[:4]]
        assert ceilings == sorted(ceilings)


def test_no_ai_roadmap_only_validates(assess):
    r = assess("banking-transaction-rules")
    assert r.roadmap.phases[0].included
    assert not any(p.included for p in r.roadmap.phases[1:])


def test_adr_contains_required_sections(assess):
    md = assess("banking-transaction-rules").adr.markdown
    for section in [
        "## Business problem", "## Current architecture", "## Constraints", "## Assumptions", "## Alternatives considered",
        "## Decision", "## Rejected alternatives", "### Reasons", "## Security implications", "## Cost implications",
        "## Risks", "## Migration approach", "## Evaluation criteria", "## Conditions requiring reassessment",
    ]:
        assert section in md, section
    assert "AGENTIC AI NOT RECOMMENDED" in md


def test_build_vs_buy_never_defaults_to_custom_build_for_no_ai(assess):
    assert assess("banking-transaction-rules").build_vs_buy.decision is SourcingDecision.KEEP
    assert assess("finops-incident-investigation").build_vs_buy.decision in {SourcingDecision.HYBRID, SourcingDecision.BUILD}


def test_model_deployment_respects_privilege(assess):
    md = assess("legal-research").model_deployment
    assert "public" not in md.recommended.lower() or "do not" in " ".join(md.rationale).lower()
    commercial = next(o for o in md.options if o.option == "Commercial LLM API")
    assert commercial.suitable is False


def test_evaluation_metrics_depend_on_architecture(assess):
    agent_metrics = {m.name for m in assess("finops-incident-investigation").evaluation.metrics}
    rag_metrics = {m.name for m in assess("legal-research").evaluation.metrics}
    assert "Tool-call success rate" in agent_metrics and "Tool-call success rate" not in rag_metrics
    assert "Citation accuracy" in rag_metrics
    assert "Groundedness (claims supported by sources)" in rag_metrics


def test_trace_captures_observability_fields(assess):
    t = assess("retail-customer-service").trace
    assert t.request_id and t.timestamp
    assert t.workflow_path[0] == "discovery" and t.workflow_path[-1] == "final_report"
    assert "Deterministic Decision Engine" in t.agents_invoked
    assert "Challenger / Validation Agent" in t.agents_invoked
    assert all(s.status == "ok" for s in t.spans)
