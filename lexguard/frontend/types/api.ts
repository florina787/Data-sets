// Typed contract mirroring backend/app/models/api.py. The UI never parses agent prose.

export type CopilotStatus =
  | "COMPLETED" | "REVIEW_REQUIRED" | "BLOCKED" | "ACCESS_DENIED" | "HUMAN_DECISION_REQUIRED" | "NEEDS_INPUT" | "HALTED" | "ERROR";

export interface Metric { label: string; value: string | number | null; tone?: "good" | "warn" | "bad" | null; hint?: string | null }
export interface Action { id: string; label: string; kind: "panel" | "copilot" | "navigate" | "review"; payload: Record<string, any> }
export interface Card {
  type: string; title: string; severity?: string | null; body?: string | null;
  metrics: Metric[]; items: any[]; actions: Action[];
}
export interface TraceStep {
  step: number; label: string; agent: string; status: "ok" | "warn" | "blocked" | "pending" | "skipped" | "error";
  detail?: string | null; duration_ms?: number | null; node?: string | null;
}
export interface Verification { pid: string; claim: string; status: string; reasons: string[]; doc_id: string | null; section_id: string | null }
export interface Evidence {
  finding_id: string; doc_id: string; doc_title: string; section_id: string; heading: string; text: string;
  highlight?: string | null;
  playbook: { result: string | null; rule_id: string | null; topic: string | null; standard_position: string | null;
              playbook_source?: { doc_id: string; section_id: string; heading: string; text: string } | null };
  verification: Verification[]; evidence_status: "VERIFIED" | "NEEDS_REVIEW";
}
export interface Finding {
  finding_id: string; doc_id: string; doc_title: string; heading: string; playbook_result: string | null;
  rule_id: string | null; topic: string | null; evidence_status: string; summary: string;
}
export interface PolicyEvidence { rule_id: string; effect: string; description: string; source_doc_id?: string | null; source_section_id?: string | null }
export interface MatterGuardResult {
  decision: string; risk: string; risk_score: number; reasons: string[]; policy_evidence: PolicyEvidence[];
  allowed_tools: string[]; blocked_tools: string[]; human_review_level: number; human_review_label: string;
  human_review_required: boolean; external_distribution: string; access_granted: boolean; ethical_wall_blocked: boolean;
  ai_allowed_for_matter: boolean; external_ai_allowed_for_matter: boolean; provider_id: string | null;
  provider_permitted: boolean | null; destination: string; alternatives: string[]; client_policy_summary?: string | null;
}
export interface Assurance {
  score: number; score_pct: number; status: string; components: Record<string, number>; weights: Record<string, number>;
  unsupported_claim_rate: number; citation_summary: Record<string, number>; blocking_issues: string[];
  stages: { stage: string; status: string; detail: string }[]; meaning: string; external_delivery_allowed: boolean;
}
export interface Approval {
  required: boolean; level: number; label: string; required_roles: string[]; reason: string;
  external_delivery_allowed: boolean; work_product_id: string;
}
export interface CopilotResponse {
  request_id: string; user_id: string; matter_id: string | null; answer: string; status: CopilotStatus; risk: string; intent: string;
  findings: Finding[]; evidence: Evidence[]; citations: any[]; playbook_deviations: any[]; actions: Action[]; cards: Card[];
  agent_trace: TraceStep[]; approval_required: boolean; approval: Approval | null; matterguard: MatterGuardResult | null;
  routing: { route: string; provider_id: string | null; workflow_id: string | null; reasons: string[]; ai_support_permitted: string[];
             options: { route: string; selected: boolean; reason: string }[] } | null;
  suitability: Record<string, any> | null; assurance: Assurance | null; privilege_flags: any[];
  sources: { doc_id: string; section_id: string; title: string; heading: string; text: string; kind: string; score?: number;
             untrusted_instruction_detected?: boolean }[];
  draft: any; work_product_id: string | null; analysis: any; review_summary: any; value_estimate: any;
  injection_flags: any[]; audit_event_ids: string[]; errors: string[];
  metrics: { latency_ms: number; est_cost_usd: number; paid_llm_calls: number; agents_invoked: string[]; tools_invoked: string[];
             tool_calls: number; graph_path: string[]; demo_mode: boolean };
}
export interface User { user_id: string; name: string; role: string; practice_id: string | null; email: string; practice?: string | null }
export interface MatterSummary {
  matter_id: string; name: string; matter_number: string; client: string; practice: string; risk_level: string | null;
  access: { permitted: boolean; reason: string; code?: string }; ai_status: string | null;
}
export interface MatterDetail {
  matter_id: string; name: string; matter_number: string; description: string; client: { client_id: string; name: string; sector: string };
  practice: string; jurisdiction: string; responsible_partner: string; current_user: string; role: string; confidentiality: string;
  risk_level: string; ethical_wall: { exists: boolean; status: string }; access_via: string | null; ai_status: string;
  ai_status_label: string; client_ai_policy: string; permitted_ai_systems: string[]; human_review: string; human_review_level: string;
  documents: { total: number; active: number; duplicates: number; unreadable: number }; team: string[];
}
export interface AuditEvent {
  event_id: string; request_id: string | null; ts: string | null; event_type: string; severity: string; user_id: string | null;
  client_id: string | null; matter_id: string | null; payload: Record<string, any>; hash: string; prev_hash: string;
}
