export interface Persona { id: string; display_name: string; role: string; tenant_id: string }
export interface Me extends Persona { account_segments: string[]; permissions: string[] }

export interface SystemInfo {
  disclaimer: string;
  app_mode: string;
  generation: { generation_mode: string; provider: string; model: string; live_calls: boolean };
  connector_mode: string;
  policy_version: string;
  dataset_version: string;
  limits: Record<string, number>;
}

export interface CaseSummary {
  id: string; title: string; status: string; status_reason: string; account_id: string; service_id: string;
  created_at: string; updated_at: string; version: number; linked_incident_id: string | null;
  investigation_running: boolean;
}

export interface PriorIntervention {
  source_ref: string; action: string; outcome: string; repeated_in_recommendation: boolean; justification: string;
}
export interface RefusedRequest { request: string; reason: string; citations: string[] }
export interface Alternative { action_type: string; allowed: boolean; executable: boolean; mvp_behavior: string; reasons: string[] }

export interface Recommendation {
  id: string; status: string; action_type: string; payload: Record<string, unknown>; payload_hash: string;
  purpose: string; prerequisites: string[]; evidence_refs: string[]; uncertainty: string; risk: string;
  approval_requirement: { requires_approval: boolean; approver_roles: string[]; executor_roles: string[];
    separation_of_duties: boolean; mvp_behavior: string };
  policy_version: string; policy_decision: { allowed: boolean; reasons: string[]; facts?: string[] };
  prior_interventions: PriorIntervention[]; refused_requests: RefusedRequest[]; alternatives: Alternative[];
  proposed_by: string; generation_mode: string; snapshot_id: string; created_at: string;
}

export interface Approval {
  id: string; case_id: string; recommendation_id: string; action_type: string; payload_hash: string;
  policy_version: string; evidence_snapshot_id: string; requested_by: string; requested_at: string;
  required_roles: string[]; separation_of_duties: boolean; status: string; decided_by: string | null;
  decided_at: string | null; decision_reason: string; expires_at: string | null;
  consumed_by_execution_id: string | null;
  case_title?: string; case_status?: string; can_decide?: boolean; expired?: boolean; wait_minutes?: number;
}

export interface Execution {
  id: string; approval_id: string; action_type: string; status: string; connector: string; connector_mode: string;
  external_ref: string | null; result: Record<string, unknown>; attempts: number; executed_by: string;
  idempotency_key: string; started_at: string; completed_at: string | null;
}

export interface Recovery {
  id: string; execution_id: string; outcome: string; reasons: string[]; healthy_samples: number;
  unhealthy_samples: number; required_samples: number; sample_ids: string[]; window_start: string;
  window_end: string; customer_report_conflict: boolean; simulation_time: boolean; checked_by: string; checked_at: string;
}

export interface SupportInteraction {
  id: string; channel: string; occurred_at: string; summary: string; notes: string; untrusted_content_flag: boolean;
  actions_taken: string[]; outcome: string; author_type: string;
}

export interface CaseDetail extends CaseSummary {
  complaint_text: string;
  reported_symptoms: Record<string, unknown>;
  customer: { id: string; display_name: string; contact_phone: string; contact_email: string };
  account: { id: string; segment: string; status: string; service_address: string; postal_area: string };
  service: { id: string; product: string; plan: string; access_technology: string; status: string };
  mapping: { id: string; asset_id: string; port: string } | null;
  equipment: { id: string; model: string; firmware: string } | null;
  support_history: SupportInteraction[];
  recommendation: Recommendation | null;
  approval: Approval | null;
  execution: Execution | null;
  recovery: Recovery | null;
}

export interface EvidenceItem {
  ref_id: string; source_type: string; source_id: string; source_version: string; authority: string;
  kind: string; excerpt: string; freshness: string; supports: string[]; opposes: string[]; flags: string[];
  retrieved_at: string; data: Record<string, unknown>;
}
export interface Hypothesis {
  rank: number; category: string; statement: string; sufficiency: string; supporting_refs: string[]; opposing_refs: string[];
}
export interface EvidenceResponse {
  snapshot: { id: string; created_at: string; content_hash: string; window_start: string; window_end: string;
    facts: string[]; missing_evidence: string[]; prior_actions: unknown[] } | null;
  items: EvidenceItem[];
  hypotheses: Hypothesis[];
  diagnosis: { conclusion: string; summary: string; validation_errors?: string[] } | null;
  snapshots: string[];
}

export interface AuditEvent {
  seq: number; event_id: string; case_id: string | null; trace_id: string; request_id: string | null;
  occurred_at: string; actor_id: string; actor_role: string; event_type: string; node: string | null;
  from_status: string | null; to_status: string | null; generation_mode: string | null; connector_mode: string | null;
  policy_version: string | null; latency_ms: number | null; usage: Record<string, unknown>;
  detail: Record<string, unknown>; prev_hash: string; event_hash: string;
}

export interface Citation { id: string; source_type: string; source_id: string; version: string; excerpt: string }
export interface ChatMessage {
  id: string; role: string; kind?: string; text: string; citations: Citation[]; generation_mode: string;
  created_at?: string;
}
