export type Unit = "count" | "percent" | "score" | "sentiment" | "ratio" | "p" | null;

export interface Metric {
  id: string;
  label: string;
  value: number | string | null;
  unit?: Unit;
  numerator?: number | null;
  denominator?: number | null;
  description?: string;
}

export interface Table<Row = Record<string, any>> {
  columns: string[];
  rows: Row[];
}

export interface DateWindow {
  start: string | null;
  end: string | null;
  label: string;
  rule: string;
  explanation: string;
}

export interface Scope {
  dataset_mode: "original" | "synthetic" | "combined";
  window: DateWindow;
  topics: string[];
  products: string[];
  domains: string[];
  agents: string[];
  sentiments: string[];
  conversation_ids: string[];
}

export interface AnalysisResult {
  operation: string;
  params: Record<string, any>;
  scope: Scope;
  metrics: Metric[];
  table: Table | null;
  series: Record<string, Table>;
  evidence_refs: string[];
  method_notes: string[];
  uncertainty_notes: string[];
  coverage: Record<string, any>;
  status: "ok" | "insufficient_data" | "unsupported" | "error";
}

export type ChartType =
  | "bar" | "horizontal_bar" | "line" | "area" | "stacked_bar" | "donut" | "heatmap" | "timeline"
  | "priority_matrix" | "scatter" | "kpi" | "table" | "error_bar";

export interface ChartSeries { key: string; label: string; color: string }

export interface ChartSpec {
  chart_id: string;
  chart_type: ChartType;
  title: string;
  description: string;
  x_field: string | null;
  y_field: string | null;
  series: ChartSeries[];
  data: Record<string, any>[];
  value_format: "count" | "percent" | "score" | "number";
  filters: Record<string, any>;
  dataset_scope: string;
  source_analysis_id: string;
  evidence_ids: string[];
  uncertainty_note: string | null;
  drilldown: { kind: "topic" | "product" | "conversation" | "agent" | "month" | "message"; field: string } | null;
  error_low_field: string | null;
  error_high_field: string | null;
  accessibility_summary: string;
}

export interface GraphSpec {
  graph_id: string;
  title: string;
  description: string;
  nodes: { id: string; label: string; kind: string; value?: number | null }[];
  edges: { source: string; target: string; weight: number; label: string; relation: "observed" | "inferred" }[];
}

export interface Excerpt {
  message_id: string;
  turn_index: number;
  role: "customer" | "agent";
  text: string;
  sentiment: string;
  act: string;
  source_reference?: string;
}

export interface Evidence {
  evidence_id: string;
  kind: "analysis" | "retrieval";
  conversation_id: string;
  message_ids: string[];
  turn_range: [number, number];
  excerpts: Excerpt[];
  topic: string;
  product: string | null;
  sentiment: string;
  agent_id: string | null;
  date: string;
  similarity: number | null;
  reason: string;
}

export interface Recommendation {
  concern: string;
  topic: string;
  rank: number;
  priority: "High" | "Medium" | "Low";
  finding: string;
  supporting_metric: { label: string; value: number; signal: string };
  rationale: string;
  suggested_action: string;
  decision_owner: string;
  evidence: string[];
  uncertainty: string;
}

export interface QACheck { check: string; passed: boolean; critical: boolean; detail: string }

export interface ChatResponse {
  version: string;
  request_id: string;
  session_id: string;
  status: "completed" | "insufficient_data" | "unsupported" | "needs_review" | "failed";
  question: string;
  resolved_intent: Record<string, any>;
  dataset_scope: Scope;
  plan: { category: string; specialist: string | null; steps: { op: string; params: any; purpose: string }[]; retrieval: any; notes: string[]; resolved_references: any; audience: string };
  headline: string;
  answer: string;
  key_points: string[];
  metrics: Metric[];
  rankings: Record<string, any>[];
  charts: ChartSpec[];
  graphs: GraphSpec[];
  evidence: Evidence[];
  recommendations: Recommendation[];
  uncertainty_notes: string[];
  method_notes: string[];
  follow_up_questions: string[];
  execution_trace_id: string;
  model_metadata: Record<string, any>;
  quality_status: { status: "pass" | "warn" | "fail"; checks: QACheck[]; passed: number; total: number };
  governance: { policy: string; outcome: string; detail: string }[];
  human_review_required: boolean;
  errors: { node: string; error: string }[];
  latency_ms?: number;
}

export type NodeStatus = "pending" | "running" | "completed" | "failed" | "skipped" | "cancelled";

export interface StreamEvent {
  type: "accepted" | "node_start" | "node_end" | "final" | "error";
  node?: string;
  label?: string;
  status?: NodeStatus;
  duration_ms?: number;
  error?: string | null;
  output_summary?: Record<string, any>;
  meta?: Record<string, any>;
  request_id?: string;
  session_id?: string;
  response?: ChatResponse;
  message?: string;
  retryable?: boolean;
}

export interface TraceNode {
  node: string;
  status: NodeStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  retries: number;
  input_summary: any;
  output_summary: any;
  error: string | null;
  meta_json: any;
}

export interface Trace {
  request: Record<string, any>;
  nodes: TraceNode[];
  llm_calls: Record<string, any>[];
}

export interface GraphDefinition {
  nodes: { id: string; label: string; role: string }[];
  edges: { source: string; target: string; conditional: boolean }[];
}
