// Mirrors the backend contract `flo.conversation/1.0` and the allowlisted visualization schema `flo.viz/1.0`.
export const VIZ_SCHEMA_VERSION = "flo.viz/1.0";
export const CHART_TYPES = ["line", "area", "stacked_area", "bar", "hbar", "stacked_bar", "grouped_bar", "combo", "waterfall", "donut", "treemap",
  "heatmap", "matrix", "scatter", "geo", "tornado", "scorecard", "agent_graph"] as const;
export type ChartType = (typeof CHART_TYPES)[number];
export type Provenance = "platform_synthetic" | "user_supplied" | "calculated_from_user_inputs" | "illustrative_assumption" | "workflow_trace";

export type Series = { name: string; values: (number | null)[]; unit: string; metric_id?: string | null; render: "auto" | "bar" | "line" | "area";
  role: "primary" | "comparison" | "baseline" | "scenario" | "limit"; stack?: string | null };
export type ChartNode = { id: string; name: string; value?: number | null; x?: number | null; y?: number | null; size?: number | null; group?: string | null;
  parent?: string | null; lat?: number | null; lon?: number | null; color_value?: number | null; status?: "ok" | "warn" | "crit" | "neutral" | "denied" | "skipped" | null;
  meta: Record<string, string | number | boolean | null> };
export type ChartLineage = { sources: string[]; methodology: string; as_of?: string | null; refreshed_at?: string | null; dataset_version?: string | null;
  semantic_layer_version?: string | null; synthetic: boolean; tools: string[] };
export type FilterSpec = { id: "months" | "group_by"; label: string; options: (string | number)[]; value: string | number };
export type ChartSpec = {
  schema_version: string; chart_id: string; chart_type: ChartType; title: string; subtitle: string;
  metrics: { id: string; name: string; definition: string; formula: string; unit: string }[];
  categories: string[]; series: Series[]; nodes: ChartNode[]; edges: { source: string; target: string; label: string }[];
  x_labels: string[]; y_labels: string[]; cells: number[][]; x_axis: { label: string; unit: string }; y_axis: { label: string; unit: string };
  unit: string; reference_lines: Record<string, string | number>[]; filters: Record<string, string | number>; available_filters: FilterSpec[];
  drilldown?: { dimension: string; prompt_template: string } | null;
  interactions: ("tooltip" | "drilldown" | "filter" | "compare" | "export" | "explain" | "methodology")[];
  lineage: ChartLineage; provenance: Provenance; agent: string; note: string;
};
export type KpiUnit = "CAD" | "%" | "bps" | "count" | "ratio" | "x" | "score" | "years";
export type KPI = { id: string; label: string; value: number | null; unit: KpiUnit; delta?: number | null; delta_unit: "%" | "pp" | "bps" | "CAD" | "count" | "";
  delta_label: string; trend: number[]; status: "good" | "warn" | "crit" | "neutral"; metric_id?: string | null; provenance: Provenance; note: string };
export type EvidenceRef = { agent: string; fact: string; value: string; tool?: string | null };
export type Insight = { id: string; section: "current_state" | "finding" | "risk" | "opportunity" | "limitation"; title: string; detail: string;
  severity: "info" | "positive" | "warning" | "critical"; evidence: EvidenceRef[] };
export type Recommendation = { id: string; title: string; priority: "P1" | "P2" | "P3"; rationale: string; evidence: EvidenceRef[]; expected_benefit: string;
  kpis: string[]; complexity: "low" | "medium" | "high"; dependencies: string[]; owner_function: string; timeframe: string; approvals_required: string[];
  validation_criteria: string[]; requires_human_review: boolean };
export type RoadmapPhase = { name: string; window: string; objectives: string[]; actions: string[]; milestones: string[]; kpis: string[]; governance_gates: string[] };
export type Table = { table_id: string; title: string; columns: string[]; rows: (string | number | boolean | null)[][]; provenance: Provenance };
export type Intent = { classifier: string; intent: string; label: string; domain: string; persona: string; identity: Record<string, unknown>;
  entities: Record<string, unknown>; metrics: string[]; time_horizon_months?: number | null; agents: string[]; agents_authorized: string[];
  agents_not_authorized: string[]; tools: string[]; data_dependencies: string[]; charts: string[]; risk_classification: string;
  approval_requirements: string[]; follow_up_of?: string | null; modifiers: Record<string, any> };
export type Stage = { id: string; label: string; status: "active" | "done"; detail: string; t_ms: number; [k: string]: unknown };
export type ToolCall = { tool: string; agent: string; decision: string; status?: string; latency_ms?: number; rule?: string; resource?: string | null };
export type MessageResponse = {
  contract_version: string; conversation_id: string; message_id: string; request_id: string;
  status: "complete" | "partial" | "denied" | "needs_input" | "rejected" | "cancelled" | "error"; question: string;
  answer: { headline: string; summary: string[]; body: string; depth: string }; persona: string; intent: Intent; insights: Insight[]; kpis: KPI[];
  charts: ChartSpec[]; tables: Table[]; recommendations: Recommendation[];
  implementation_plan?: { title: string; basis: string; phases: RoadmapPhase[] } | null;
  citations: { document_id: string; title: string; section: string; version: string }[];
  data_freshness: { as_of?: string | null; refreshed_at?: string | null; dataset_version?: string | null; synthetic: boolean; sources: string[] };
  assumptions: { name: string; value: string | number | null; unit: string; source: string }[]; warnings: string[];
  approval_requirements: { action: string; reason: string; approver_roles: string[]; status: "required" | "pending" | "approved" | "not_permitted"; approval_id?: string | null }[];
  suggested_followups: string[]; discovery?: { known: string[]; missing: string[]; questions: string[]; integrations: { system: string; data: string; enables: string }[] } | null;
  trace_id?: string | null; trace_ids: string[];
  workflow: { workflow_id?: string | null; route?: string | null; agents: string[]; tool_calls: ToolCall[]; policy_decisions: { action: string; allowed: boolean }[];
    errors: { agent: string; failure_class: string; message?: string }[]; model: string; model_mode: string; injection?: { flagged: boolean; severity?: string } | null;
    stages: Stage[]; latency_ms?: number | null; graph?: ChartSpec | null };
  created_at: string;
};
export type Persona = { id: string; label: string; short: string; description: string; typical_roles: string[]; depth: string; terminology: string;
  emphasis: string[]; owner_functions: string[]; prompts: string[]; default_intent: string; aligned_with_identity: boolean };
export type PersonaCatalogue = { starter_prompts: string[]; default: string; note: string; personas: Persona[] };
export type ConversationSummary = { id: string; persona: string; title: string; created_at: string; updated_at: string; message_count: number;
  last_intent?: string | null; last_question?: string | null };
export type StoredMessage = { id: string; role: "user" | "assistant"; content: string; status: string; intent?: string | null; created_at: string;
  request_id?: string | null; response?: MessageResponse | null };
export type MessageContext = { months?: number; group_by?: string; client_id?: string; scenario?: { preset?: string; equity_shock?: number; rate_shock_bps?: number };
  focus?: string; intent?: string; chart_id?: string };

// live events from the Server-Sent Events stream
export type LiveEvent =
  | { type: "started"; data: { conversation_id: string; message_id: string; request_id: string } }
  | { type: "stage"; data: Stage }
  | { type: "intent"; data: Intent }
  | { type: "plan"; data: { supervisor: string; agents: string[]; skipped: string[] } }
  | { type: "agent"; data: { agent: string; status: "succeeded" | "failed"; tools?: string[]; failure_class?: string } }
  | { type: "error"; data: { code: string; message: string } };
