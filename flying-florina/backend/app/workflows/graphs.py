"""Workflow graph definitions (Graph 1 maintenance, Graph 2 legacy, Graph 3 governance and others)."""

from __future__ import annotations

from app.agents import analytics as an
from app.agents import maintenance as mx
from app.workflows.engine import Graph, Step

INTAKE = "Intake & Intent Agent"
SUP = "Supervisor Agent"
SEC = "Security & Governance Agent"


def maintenance_graph() -> Graph:
    return Graph("maintenance_investigation", [
        Step("intake", INTAKE, mx.intake, description="Normalize aircraft, type, base, part"),
        Step("policy_precheck", SEC, mx.policy_precheck, ["intake"], description="Identity and policy precheck"),
        Step("telemetry", "Asset Telemetry Agent", mx.telemetry, ["policy_precheck"], description="Time-series stats, outliers, data quality"),
        Step("retrieval", "Knowledge Retrieval Agent", mx.retrieval, ["policy_precheck"], description="Access-filtered hybrid search with citations"),
        Step("history", "Diagnostic Evidence Agent", mx.history, ["policy_precheck"], description="Maintenance history"),
        Step("diagnostics", "Diagnostic Evidence Agent", mx.diagnostics, ["telemetry", "retrieval", "history"], description="Hypotheses with uncertainty"),
        Step("parts", "Parts Agent", mx.parts, ["diagnostics"], description="Verified inventory and approved alternates"),
        Step("scheduling", "Maintenance Planner Agent", mx.scheduling, ["diagnostics"], description="Qualified technicians and slots"),
        Step("compliance", "Compliance Agent", mx.compliance, ["parts", "scheduling"], description="Evidence sufficiency checklist"),
        Step("draft_plan", "Maintenance Planner Agent", mx.draft_plan, ["compliance"], description="Dry-run work order draft"),
        Step("approval_gate", SEC, mx.approval_gate, ["draft_plan"], retries=0, description="Human approval request (separation of duties)"),
    ])


def recovery_graph() -> Graph:
    g = maintenance_graph()
    return Graph("recovery_options", [s for s in g.steps if s.name not in ("draft_plan", "approval_gate")] + [
        Step("scenario_inputs", "Scenario Simulator Agent", an.scenario_inputs, ["compliance"], description="Delay scenarios 24/48/72 h"),
        Step("scenario_run", "Scenario Simulator Agent", an.scenario_run, ["scenario_inputs"], description="Deterministic + seeded Monte Carlo"),
    ])


def scenario_graph() -> Graph:
    return Graph("scenario_compare", [
        Step("policy_precheck", SEC, an.precheck("simulate"), description="Identity and policy precheck"),
        Step("scenario_inputs", "Scenario Simulator Agent", an.scenario_inputs, ["policy_precheck"], description="Normalize assumptions"),
        Step("scenario_run", "Scenario Simulator Agent", an.scenario_run, ["scenario_inputs"], description="Compute outcomes, Monte Carlo, sensitivity"),
    ])


def downtime_graph() -> Graph:
    return Graph("downtime_analysis", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("trend", "Asset Telemetry Agent", an.downtime_trend, ["policy_precheck"], description="Monthly downtime normalized per aircraft-day"),
        Step("causes", "Diagnostic Evidence Agent", an.downtime_causes, ["trend"], description="Cause decomposition vs baseline"),
        Step("statistics", "Diagnostic Evidence Agent", an.downtime_stats, ["trend"], description="Bootstrap confidence intervals"),
    ])


def legacy_graph() -> Graph:
    return Graph("legacy_assessment", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("metadata_import", "Legacy Discovery Agent", an.legacy_import, ["policy_precheck"], description="Parse schemas, APIs, files (no execution)"),
        Step("dependency_graph", "Legacy Discovery Agent", an.legacy_graph, ["metadata_import"], description="System dependency graph"),
        Step("risk_classification", SEC, an.legacy_risks, ["dependency_graph"], description="Risks, classification, unknowns"),
        Step("integration_options", "Integration Architect Agent", an.legacy_options, ["risk_classification"], description="REST/OData/events/batch/facade/MCP"),
        Step("target_architecture", "Integration Architect Agent", an.legacy_target, ["integration_options"], description="Target state + roadmap"),
        Step("adapter_generation", "Integration Architect Agent", an.adapter_preview, ["target_architecture"], description="Generate adapter preview"),
        Step("contract_tests", "Integration Architect Agent", an.contract_static, ["adapter_generation"], description="Static contract/security checks"),
        Step("security_review", SEC, an.security_review, ["contract_tests"], description="High-severity review"),
    ])


def bridge_graph() -> Graph:
    return Graph("bridge_generation", [
        Step("policy_precheck", SEC, an.precheck("generate_code"), description="Code generation permission"),
        Step("discover", "Integration Architect Agent", an.bridge_discover, ["policy_precheck"], description="Discover metadata, select capability"),
        Step("generate", "Integration Architect Agent", an.bridge_generate, ["discover"], description="Generate adapter, MCP tool, tests"),
        Step("static_checks", SEC, an.contract_static, ["generate"], description="Static checks (no execution)"),
    ])


def governance_graph() -> Graph:
    return Graph("governance_review", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("decisions", SEC, an.governance_summary, ["policy_precheck"], description="Collect denied decisions"),
    ])


def export_graph() -> Graph:
    return Graph("data_export", [
        Step("identity_policy", SEC, an.export_attempt, retries=0, description="Identity + policy evaluation before any tool runs"),
    ])


def documents_graph() -> Graph:
    return Graph("document_freshness", [
        Step("policy_precheck", SEC, an.precheck("query", "PUBLIC"), description="Identity and policy precheck"),
        Step("freshness", "Compliance Agent", an.doc_freshness, ["policy_precheck"], description="Revision, review date, provenance"),
    ])


def executive_graph() -> Graph:
    return Graph("executive_pitch", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("findings", "Reporting Agent", an.exec_findings, ["policy_precheck"], description="Validated findings from read models"),
        Step("roi", "Scenario Simulator Agent", an.exec_roi, ["findings"], description="Transparent ROI model"),
        Step("brief", "Reporting Agent", an.exec_report, ["roi"], description="PDF/MD/HTML executive brief"),
    ])


def parts_graph() -> Graph:
    return Graph("parts_status", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("parts", "Parts Agent", an.parts_overview, ["policy_precheck"], description="Critical stock and supplier reliability"),
    ])


def fleet_graph() -> Graph:
    return Graph("fleet_overview", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("fleet", "Asset Telemetry Agent", an.fleet_summary, ["policy_precheck"], description="Fleet health read model"),
    ])


def quality_graph() -> Graph:
    return Graph("quality_investigation", [
        Step("policy_precheck", SEC, an.precheck("query"), description="Identity and policy precheck"),
        Step("ncr", "Compliance Agent", an.quality_ncr, ["policy_precheck"], description="NCR evidence and CAPA draft"),
    ])


GRAPHS = {
    "maintenance_investigation": maintenance_graph,
    "recovery_options": recovery_graph,
    "scenario_compare": scenario_graph,
    "downtime_analysis": downtime_graph,
    "legacy_assessment": legacy_graph,
    "bridge_generation": bridge_graph,
    "governance_review": governance_graph,
    "data_export": export_graph,
    "document_freshness": documents_graph,
    "executive_pitch": executive_graph,
    "parts_status": parts_graph,
    "fleet_overview": fleet_graph,
    "quality_investigation": quality_graph,
}
