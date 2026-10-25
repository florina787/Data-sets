export type Envelope<T> = {
  request_id: string;
  data: T;
  warnings: string[];
  provenance: Record<string, unknown>;
  demo: { demo_mode: boolean; offline_mode: boolean; synthetic_data: boolean; live_ifs_connection: boolean };
  timestamp: string;
};

export type Actor = { id: string; display_name: string; role: string; org: string; clearances: string[]; persona: string };

export type Persona = { user_id: string; persona: string; role: string; focus: string; default_page: string };

export type ChartSpec = {
  kind: "line" | "bar" | "pie";
  x: (string | number)[];
  series: { name: string; data: (number | null)[] }[];
  markLine?: { y: number; label: string } | null;
  yLabel?: string;
};

export type Block =
  | { type: "answer"; markdown: string }
  | { type: "kpis"; items: { label: string; value: string | number; tone?: string; hint?: string }[] }
  | { type: "chart"; id: string; title: string; caption?: string; source?: string; chart: ChartSpec }
  | { type: "table"; title: string; caption?: string; columns: { key: string; label: string }[]; rows: Record<string, unknown>[] }
  | { type: "citations"; items: Citation[] }
  | { type: "warnings"; items: string[] }
  | { type: "assumptions"; items: string[] }
  | { type: "policy"; decisions: Decision[]; allowed: number; denied: number }
  | { type: "approval"; items: ApprovalRef[] }
  | { type: "artifacts"; items: { kind: string; id: string; title: string; fmt?: string }[] }
  | { type: "actions"; items: { label: string; kind: string; target: string }[] }
  | { type: "clarify"; suggestions: string[] }
  | { type: "graph"; title: string; nodes: GraphNode[]; edges: GraphEdge[] }
  | { type: "recommendations"; items: Recommendation[] }
  | { type: "roadmap"; items: RoadmapPhase[] }
  | { type: "formulas"; items: string[] }
  | { type: "scenario_controls"; inputs: Record<string, unknown> }
  | { type: "roi_controls"; inputs: Record<string, unknown> }
  | { type: "code"; title: string; language: string; code: string }
  | { type: "bridge_test"; bundle_id: string }
  | { type: "decision_trace"; decision: Decision; identity: Actor; classification: string; destination: string };

export type Citation = {
  doc_id: string; title: string; revision: string; effective_date: string; review_due: string; classification: string;
  source: string; status: string; provenance_sha256: string | null; snippet: string; score: number; flags: string[]; authoritative: boolean;
};

export type Decision = {
  id: string; decision: "ALLOW" | "DENY"; policy_id: string; reason: string; ts: string; actor: string; role: string;
  action: string; resource: string; label: string; destination: string; tool?: string | null;
  checks: { policy_id: string; name: string; result: string; detail: string }[];
};

export type ApprovalRef = { id: string; kind: string; title: string; status: string; expires_at: string; payload_sha256: string; requested_by: string; idempotency_key: string };

export type GraphNode = { id: string; label: string; type: string; confidence?: number; evidence?: string[]; criticality?: string; kind?: string; why?: string; parent?: string | null };
export type GraphEdge = { id: string; source: string; target: string; label: string; kind: string; confidence?: number };

export type Recommendation = {
  id: string; pattern: string; title: string; why: string; prerequisites: string[]; evidence: string[]; security_classification: string;
  dependencies: string[]; migration_risk: string; implementation_steps: string[]; rollback: string; test_plan: string[];
  effort_assumption: string; tradeoffs: string; confidence: number; human_decisions: string[]; applies: boolean;
  diagram: { nodes: string[]; edges: number[][] };
};

export type RoadmapPhase = { phase: string; owner: string; items: string[]; dependencies: string[]; exit: string };

export type WorkflowEvent = { id: number; run_id: string; step: string; agent: string; status: string; ts: string; attempt: number; duration_ms: number | null; summary: string; detail: Record<string, unknown> };

export type RunView = {
  run_id: string; session_id: string; workflow: string; status: string; query: string; finished: boolean; replay_of?: string | null;
  state: {
    answer: string; workspace: Block[]; warnings: string[]; assumptions: string[]; retrieved_docs: Citation[]; policy_decisions: Decision[];
    approvals: ApprovalRef[]; timing: { total_ms?: number; demo_pacing_ms?: number }; costs: Record<string, unknown>; intent: { confidence: number; scores: Record<string, number> };
    tool_calls: { agent: string; tool: string; status: string }[]; errors: { step: string; error: string }[]; persona: string;
  };
  graph: { name: string; nodes: { id: string; agent: string; deps: string[]; description: string }[] } | null;
  events: WorkflowEvent[];
  options: Record<string, unknown>;
  reproducibility?: { identical_fields: Record<string, boolean>; note: string };
};
