// Typed API client. Demo mode authenticates with per-role demo tokens issued by the backend's synthetic tenant.
export type Role = "viewer" | "operator" | "approver" | "admin";
export const ROLES: Role[] = ["viewer", "operator", "approver", "admin"];
const TENANT = "meridian";
let currentRole: Role = (localStorage.getItem("florome.role") as Role) || "operator";
const listeners = new Set<() => void>();

export function getRole(): Role {
  return currentRole;
}
export function setRole(r: Role) {
  currentRole = r;
  localStorage.setItem("florome.role", r);
  listeners.forEach((l) => l());
}
export function onRoleChange(fn: () => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init: RequestInit & { role?: Role } = {}): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer demo-${TENANT}-${init.role ?? currentRole}`, ...(init.headers || {}) },
  });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, (body && (typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail))) || res.statusText);
  return body as T;
}

export const post = <T,>(path: string, body?: unknown, role?: Role) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), role });

export function nonce(): string {
  const a = new Uint8Array(16);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}

// ---------------------------------------------------------------------------------------------- types
export interface TopoNode { id: string; name: string; kind: string; platform: string; environment: string; health: string; incident: { incident_id: string; role: string } | null }
export interface Topology { nodes: TopoNode[]; edges: { source: string; target: string; kind: string }[]; data_mode: string }
export interface Incident { id: string; title: string; severity: string; status: string; primary_resource_id: string; detected_at: string; resolved_at: string | null; symptoms: string[]; is_demo: boolean; source_system?: string }
export interface HypTest { test: string; result: "pass" | "fail" | "unknown"; detail: string; evidence: string[] }
export interface Hypothesis { id: string; kind: string; role: string; title: string; candidate_resource_id: string; related_resource_id: string | null; status: Status; basis: string; tests: HypTest[]; supporting_evidence: string[]; contradicting_evidence: string[] }
export type Status = "confirmed" | "probable" | "inconclusive" | "disproven";
export interface TimelineItem { evidence_id: string; resource_id: string; resource: string; kind: string; at: string; summary: string; anomalous: boolean }
export interface RCAReport {
  id: string; report_hash: string; created_at: string; integrity_ok?: boolean; data_mode: string;
  incident: { id: string; title: string; primary_resource_id: string; detected_at: string };
  hypotheses: Hypothesis[]; timeline: TimelineItem[]; scope: string[]; anomaly_onset: Record<string, string>;
  conclusion: { status: Status; final_status: Status; statement: string; root_hypothesis_id: string | null; root_resource_id: string | null; causal_chain: { resource_id: string; link_status: string; hypothesis_id: string | null }[]; competing_hypotheses: string[]; next_diagnostics: string[] };
  challenge: { checks: { check: string; status: string; detail: string }[]; original_status: Status; final_status: Status; downgraded_by: string[] };
  affected_systems: { resource_id: string; name: string; platform: string; kind: string; role: string }[];
  business_impact: { name: string }[];
  evidence_graph: { nodes: { id: string; type: string; label: string; status?: string; platform?: string; kind?: string; anomalous?: boolean; role?: string }[]; edges: { source: string; target: string; type: string }[] };
  recommended_remediation: { action: string; target: string; params: Record<string, unknown>; risk: string }[];
  remediation_notes: string[]; risks: string[]; validation_procedure: string[]; preventive_measures: string[];
  evidence_collection: { collected: number; errors: string[]; unsupported: string[] };
}
export interface PlanStep { index: number; action_id: string; title: string; target_name: string; target_kind: string; environment: string; params: Record<string, unknown>; expected_outcome: string; risk: string; reversible: boolean; rollback: string; required_permission: string; rationale: string; simulated: boolean; status?: string; message?: string }
export interface Plan {
  id: string; incident_id: string; status: string; steps: PlanStep[]; plan_hash: string; risk: string; requires_approval: boolean; created_by: string; created_at: string; current_step: number; last_error: string | null;
  policy_decision: { reasons: string[]; notes: string[]; validation_targets: string[]; rca_status: string };
  approvals: { id: string; approver_id: string; decision: string; created_at: string; expires_at: string }[];
  validations: { id: string; passed: boolean; checks: { resource: string; check: string; passed: boolean; observed?: unknown; threshold?: unknown; expected?: unknown }[]; created_at: string }[];
}
export interface Execution { id: string; plan_id: string; step_index: number; action_id: string; status: string; attempts: number; started_at: string; finished_at: string | null; result: { message?: string; success?: boolean }; error: string | null; executed_by: string }
export interface Summary {
  data_mode: string; emergency_stop: boolean;
  connections: { verified: number; total: number; platforms_verified: string[] };
  incidents: { open: number; resolved: number; by_status: Record<string, number> };
  rca: { by_conclusion: Record<string, number> };
  remediation: { pending_approval: number; by_status: Record<string, number> };
  executions: { succeeded: number; failed: number };
  cost: { period: string | null; amount: number; previous: number; is_demo: boolean };
}
export interface Platform { platform: string; group: string; status: "implemented" | "simulated" | "not_implemented"; connector_type: string; note: string; connected_and_verified: boolean }
export interface McpTool { id: string; server_id: string; name: string; description: string; input_schema: { properties?: Record<string, { type?: string }>; required?: string[] }; access: string; enabled: boolean; quarantine_reason: string | null; schema_hash: string }
export interface AuditItem { id: string; seq: number; at: string; actor: string; action: string; target: string; outcome: string; detail: Record<string, unknown>; hash: string }

// ------------------------------------------------------------------------------------------- Florome Shield
export interface ShieldSummary {
  repositories: number;
  hypotheses: { total: number; by_status: Record<string, number> };
  findings: { confirmed: number; by_severity: Record<string, number>; by_class: Record<string, number>; incidents_opened: number };
  patches: Record<string, number>;
  containment: { sessions: number; contained: number; by_violation: Record<string, number> };
  policy: { decisions: number; denied: number };
  controls: { opengrep: boolean; trivy: boolean; opa: boolean; opa_mode: string; network_namespace: boolean; emergency_stop: boolean; rate_limit_per_minute: number };
  data_class: string;
}
export interface ShieldRepo { id: string; name: string; data_class: string; latest_snapshot: { id: string; commit: string | null; tree_hash: string; stats: Record<string, number> } | null }
export interface Evidence { type: string; ref: string; detail: string }
export interface ShieldHyp {
  id: string; vuln_class: string; function: string; file: string; line: number; status: string; status_basis: string; assumption: string; weakness: string;
  verification_method: string | null; supporting: Evidence[]; contradicting: Evidence[]; severity: string | null; severity_basis: string | null; incident_id: string | null;
  verification_runs?: { id: string; purpose: string; attempt: number; outcome: string; seconds: number; isolation: { network_namespace?: boolean }; transcript: { probe?: { evidence?: string; requests?: { path: string; params: unknown; status: number }[] } } }[];
  patches?: { id: string; status: string; diff: string; regression: { exploit_blocked_runs: number; functional_ok: boolean }; patch_hash: string; requested_by: string; reviewed_by: string | null }[];
  source?: { start_line: number; lines: string[]; highlight: number; commit: string | null };
}
export interface GraphNode { id: string; kind: string; name: string; qualname: string; file: string; line: number; route: { method: string; path: string } | null; trust_boundary: string | null; auth_provider: boolean; findings: { id: string; class: string; status: string }[] }
export interface CodeGraph { snapshot: { id: string; commit: string | null; tree_hash: string } | null; nodes: GraphNode[]; edges: { id: string; kind: string; source: string; target: string; line: number; attrs: Record<string, unknown>; provenance: Record<string, string> }[] }
export interface ContainmentEvent { id: string; session_id: string; scenario: string; violation: string | null; outcome: string; actions_taken: string[]; forensics: { seconds: number; returncode: number; matched_expectation: boolean; guard_events: { violation: string; detail: string }[]; expected: string }; at: string }
export interface BenchRow { id: string; pipeline: string; status: string; sample_size: number; metrics: Record<string, any>; note: string; at: string }

// ------------------------------------------------------------------------------------------- Assistant
export type AssistantVisual =
  | { type: "kpis"; items: { label: string; value: number | string }[] }
  | { type: "bars"; unit: string; items: { label: string; value: number }[] }
  | { type: "chain"; items: { label: string; tone: string; note?: string }[] }
  | { type: "table"; columns: string[]; rows: (string | number)[][] }
  | { type: "timeline"; items: { at: string; label: string; text: string; tone: string }[] }
  | { type: "report"; markdown: string };
export interface AssistantAnswer {
  conversation_id: string; intent: string | null; statement: string; bullets: string[]; visual: AssistantVisual | null;
  evidence: { label: string; href: string | null }[]; follow_ups: string[]; engine: { mode: string; language_model: string | null };
  input_flags: string[]; data_mode: string;
  source: { name: string; status: string; model_calls: number | null; content_flags?: string[] };
}
export interface AssistantPage {
  page: string; title: string; starters: string[]; engine: { mode: string; language_model: string | null };
  groups?: { title: string; questions: string[] }[];
}
export interface AssistantSources { florome: { reachable: boolean; status: string }; conversation_copilot: { configured: boolean; reachable: boolean; status: string } }
