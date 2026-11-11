import type { Plan, RCAReport, Summary, Topology } from "../lib/api";

export const topology: Topology = {
  data_mode: "demo",
  nodes: [
    { id: "a", name: "ingest-orders", kind: "lambda", platform: "aws", environment: "prod", health: "failed", incident: { incident_id: "i1", role: "root" } },
    { id: "b", name: "orders-etl", kind: "databricks_job", platform: "databricks", environment: "prod", health: "failed", incident: { incident_id: "i1", role: "impacted" } },
    { id: "c", name: "revenue-api", kind: "app_service", platform: "azure", environment: "prod", health: "failed", incident: { incident_id: "i1", role: "symptom" } },
    { id: "d", name: "customer-portal", kind: "app_service", platform: "azure", environment: "prod", health: "healthy", incident: null },
  ],
  edges: [{ source: "a", target: "b", kind: "data_flow" }, { source: "b", target: "c", kind: "data_flow" }],
};

export const summary: Summary = {
  data_mode: "demo", emergency_stop: false,
  connections: { verified: 1, total: 1, platforms_verified: ["sandbox"] },
  incidents: { open: 1, resolved: 0, by_status: { open: 1 } }, rca: { by_conclusion: {} },
  remediation: { pending_approval: 1, by_status: {} }, executions: { succeeded: 0, failed: 0 },
  cost: { period: "2026-10", amount: 27000, previous: 24000, is_demo: true },
};

export const plan: Plan = {
  id: "plan_1", incident_id: "i1", status: "pending_approval", plan_hash: "a".repeat(64), risk: "medium", requires_approval: true,
  created_by: "u-meridian-operator", created_at: "2026-11-10T12:00:00Z", current_step: 0, last_error: null,
  policy_decision: { reasons: ["Human approval required: tenant policy is approval mode."], notes: [], validation_targets: [], rca_status: "confirmed" },
  approvals: [], validations: [],
  steps: [{ index: 0, action_id: "rollback_deployment", title: "Roll back deployment", target_name: "ingest-orders", target_kind: "lambda", environment: "prod",
    params: { to_version: "v2.13.4" }, expected_outcome: "Errors drop", risk: "medium", reversible: true, rollback: "Re-point alias",
    required_permission: "lambda:UpdateAlias", rationale: "H3 confirmed", simulated: true, status: "pending" }],
};

export const report = {
  id: "rca_1", report_hash: "b".repeat(64), created_at: "2026-11-10T12:00:00Z", data_mode: "demo",
  incident: { id: "i1", title: "x", primary_resource_id: "c", detected_at: "2026-11-10T12:00:00Z" },
  scope: ["a", "b", "c"], anomaly_onset: {},
  hypotheses: [
    { id: "H1", kind: "change", role: "root_cause", title: "Deployment on ingest-orders", candidate_resource_id: "a", related_resource_id: null, status: "confirmed", basis: "Passed: all", tests: [], supporting_evidence: ["ev_1"], contradicting_evidence: [] },
    { id: "H2", kind: "change", role: "root_cause", title: "Config change on revenue-api", candidate_resource_id: "c", related_resource_id: null, status: "disproven", basis: "", tests: [], supporting_evidence: [], contradicting_evidence: ["ev_2"] },
  ],
  timeline: [
    { evidence_id: "ev_1", resource_id: "a", resource: "ingest-orders", kind: "deployment", at: "2026-11-10T11:10:00Z", summary: "deployed", anomalous: false },
    { evidence_id: "ev_2", resource_id: "c", resource: "revenue-api", kind: "log", at: "2026-11-10T11:40:00Z", summary: "500", anomalous: true },
  ],
  conclusion: { status: "confirmed", final_status: "confirmed", statement: "Deployment on ingest-orders.", root_hypothesis_id: "H1", root_resource_id: "a", causal_chain: [], competing_hypotheses: [], next_diagnostics: [] },
  challenge: { checks: [], original_status: "confirmed", final_status: "confirmed", downgraded_by: [] },
  affected_systems: [], business_impact: [],
  evidence_graph: {
    nodes: [{ id: "a", type: "resource", label: "ingest-orders" }, { id: "H1", type: "hypothesis", label: "Deployment", status: "confirmed" },
      { id: "H2", type: "hypothesis", label: "Config", status: "disproven" }, { id: "ev_1", type: "evidence", label: "deployed" }, { id: "ev_2", type: "evidence", label: "500" }],
    edges: [{ source: "H1", target: "a", type: "about" }, { source: "ev_1", target: "H1", type: "supports" }, { source: "ev_2", target: "H2", type: "contradicts" }],
  },
  recommended_remediation: [], remediation_notes: [], risks: [], validation_procedure: [], preventive_measures: [],
  evidence_collection: { collected: 2, errors: [], unsupported: [] },
} as unknown as RCAReport;
