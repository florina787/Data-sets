// Typed client for the MedAccess AI backend. The frontend never holds provider API keys:
// it only talks to the backend, which owns all secrets.

export type Role = "patient" | "engineer" | "release_approver" | "admin";

export interface User {
  id: string;
  role: Role;
  name: string;
  permissions: string[];
}

export type AvailabilityStatus =
  | "VERIFIED_AVAILABLE"
  | "ADVERTISED_UNVERIFIED"
  | "CONTACT_REQUIRED"
  | "UNAVAILABLE"
  | "UNKNOWN"
  | "DEMO_SIMULATED";

export interface Recommendation {
  rank: number;
  tier: "CONFIRMED_ALTERNATIVE" | "UNVERIFIED_POSSIBILITY";
  facility_id: string;
  facility_name: string;
  slot_id: string;
  service: string;
  start_local: string | null;
  days_until: number | null;
  days_saved: number | null;
  straight_km: number;
  est_driving_minutes: number;
  verification_status: AvailabilityStatus;
  display_status: AvailabilityStatus;
  eligibility_status: string;
  reasons: string[];
  source_id: string;
  last_verified_at: string | null;
  is_synthetic: boolean;
  booking_capability: string;
}

export interface FacilitySummary {
  id: string;
  name: string;
  city: string;
  neighbourhood: string;
  latitude: number;
  longitude: number;
  phone: string;
  booking_url: string | null;
  booking_capability: string;
  funding: string;
  wheelchair_accessible: boolean;
  is_synthetic: boolean;
  network: string;
}

export interface Eligibility {
  facility_id: string;
  status: string;
  requisition_required: boolean;
  referral_required: boolean;
  coverage_note: string;
  reasons: string[];
  actions: string[];
}

export interface VerifiedSlot {
  slot_id: string;
  facility_id: string;
  service: string;
  start_local: string | null;
  source_id: string;
  source_status: string;
  verification_status: AvailabilityStatus;
  display_status: AvailabilityStatus;
  verification_reasons: string[];
  last_verified_at: string | null;
  data_age_hours: number | null;
  is_synthetic: boolean;
}

export interface FacilityCard {
  facility: FacilitySummary;
  geo: { straight_km: number; est_driving_minutes: number; est_transit_minutes: number | null; transit_accessible: boolean; method: string };
  eligibility: Eligibility | null;
  best_slot: VerifiedSlot | null;
  days_until: number | null;
  slot_count: number;
  source_status: string;
  availability_state: AvailabilityStatus;
}

export interface TraceEntry {
  node: string;
  agent: string;
  title: string;
  status: string;
  action: string;
  duration_ms: number;
  at: string;
}

export interface WorkflowResult {
  workflow_id: string;
  workflow_status: string;
  requested_service: string | null;
  search_location: string | null;
  latitude: number | null;
  longitude: number | null;
  radius_km: number | null;
  existing_appointment: { date?: string; days_until?: number } | null;
  recommendations: Recommendation[];
  facility_cards: FacilityCard[];
  wait_summary: { existing_wait_days: number | null; best_confirmed_days: number | null; potential_days_saved: number | null; confirmed_count: number; unverified_count: number; basis: string };
  explanation: string | null;
  agent_trace: TraceEntry[];
  errors: string[];
  unavailable_sources: string[];
  verification_status: { counts?: Record<string, number>; status_mapping?: string; build_version?: string; duplicates_removed?: string[] };
  data_quality: Record<string, unknown>;
  source_references: { source_id: string; kind: string; title: string }[];
  pending_question: { type: string; approval_id: string; options?: { radius_km: number; facilities_offering_service: number }[] } | null;
  approval_id: string | null;
  booking_status: string;
  booking: Record<string, any>;
  safety: { interrupt?: boolean; flags?: string[]; message?: string | null };
  security_events: { type: string }[];
  build_version: string;
  data_mode: string;
  notice: string | null;
  duration_ms: number;
  trace_id: string | null;
  request_id: string | null;
  missing_fields: string[];
  retry_count: number;
  token_usage: number;
}

export interface ChatReply {
  session_id: string;
  reply: string;
  avatar_state: AvatarState;
  quick_replies: string[];
  workflow: WorkflowResult | null;
  citations: { document_id: string; title: string; heading: string; source_url: string | null; provider: string; stale: boolean; access_classification: string }[];
  warnings: string[];
  safety: Record<string, unknown> | null;
  mode: string;
  disclaimer: string;
}

export type AvatarState = "greeting" | "idle" | "thinking" | "speaking" | "pointing" | "celebrating" | "explaining" | "warning";

export interface Approval {
  id: string;
  action_type: string;
  workflow_id: string | null;
  workflow_type: string;
  requesting_agent: string;
  reason: string;
  evidence: Record<string, unknown>[];
  consequences: string[];
  payload: Record<string, any>;
  status: string;
  decided_by: string | null;
  created_at: string;
  required_role: string;
}

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public requestId?: string | null) {
    super(message);
  }
}

const TOKEN_KEY = "medaccess.token";
let memoryToken: string | null = null;

export function getToken(): string | null {
  if (memoryToken) return memoryToken;
  try {
    memoryToken = sessionStorage.getItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
  return memoryToken;
}

export function setToken(t: string | null) {
  memoryToken = t;
  try {
    if (t) sessionStorage.setItem(TOKEN_KEY, t);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const t = getToken();
  if (t) headers.Authorization = `Bearer ${t}`;
  const res = await fetch(`/api/v1${path}`, {
    method: opts.method ?? (opts.body !== undefined ? "POST" : "GET"),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const e = data?.error ?? {};
    throw new ApiError(res.status, e.code ?? "HTTP_ERROR", e.message ?? res.statusText, e.request_id);
  }
  return data as T;
}

export const endpoints = {
  login: (user_id: string) => api<{ access_token: string; user: User }>("/auth/demo-login", { body: { user_id } }),
  demoUsers: () => api<{ items: { id: string; name: string; role: Role }[] }>("/auth/demo-users"),
  config: () => api("/config/public"),
  greet: (session_id?: string) => api<ChatReply>("/copilot/greet", { body: { session_id } }),
  chat: (message: string, session_id?: string, scenario?: string | null) =>
    api<ChatReply>("/copilot/chat", { body: { message, session_id, scenario: scenario || null } }),
  search: (body: Record<string, unknown>) => api<WorkflowResult>("/search/appointments", { body }),
  facilities: (q = "") => api(`/facilities${q}`),
  dashboard: () => api("/dashboard"),
  workflow: (id: string) => api<WorkflowResult>(`/workflows/${id}`),
  requestBooking: (body: Record<string, unknown>) => api("/bookings/request", { body }),
  bookings: () => api<{ items: any[] }>("/bookings"),
  patientReported: (id: string) => api(`/bookings/${id}/patient-reported`, { method: "POST" }),
  approvals: (status = "PENDING") => api<{ items: Approval[] }>(`/approvals${status ? `?status=${status}` : "?status="}`),
  decide: (id: string, body: Record<string, unknown>) => api(`/approvals/${id}/decision`, { body }),
  notifications: () => api("/notifications"),
  consents: () => api("/consents"),
  setConsent: (consent_type: string, granted: boolean) => api("/consents", { body: { consent_type, granted } }),
  prefs: () => api("/preferences"),
  savePrefs: (body: Record<string, unknown>) => api("/preferences", { method: "PUT", body }),
  history: (saved = false) => api<{ items: any[] }>(`/searches/history${saved ? "?saved=true" : ""}`),
  saveSearch: (id: string) => api(`/searches/${id}/save`, { method: "POST" }),
  deleteMyData: () => api("/me/data", { method: "DELETE" }),
  knowledgeDocs: () => api("/knowledge/documents"),
  knowledge: (q: string) => api(`/knowledge/search?q=${encodeURIComponent(q)}`),
  graph: () => api("/graphs/patient"),
  agents: () => api("/agents"),
  agentMetrics: () => api("/agents/metrics"),
  sdlcStart: (simulation_volume: number) => api("/sdlc/demo/start", { body: { simulation_volume } }),
  sdlcRun: (id: string) => api(`/sdlc/demo/${id}`),
  sdlcRuns: () => api("/sdlc/runs"),
  sdlcTrace: (id: string) => api(`/sdlc/demo/${id}/traceability`),
  sdlcArtifact: (id: string, stage: string) => api(`/sdlc/demo/${id}/artifacts/${stage}`),
  analyze: (requirement: string) => api("/sdlc/requirements/analyze", { body: { requirement } }),
  requirements: () => api("/sdlc/requirements"),
  architecture: () => api("/sdlc/architecture"),
  runTests: (build_version?: string) => api("/sdlc/tests/run", { body: { build_version: build_version || null } }),
  pytestReport: () => api("/sdlc/tests/pytest-report"),
  securityScan: () => api("/sdlc/security/scan", { method: "POST" }),
  simulate: (body: Record<string, unknown>) => api("/sdlc/simulations", { body }),
  anomalies: () => api("/sdlc/anomalies"),
  detect: () => api("/sdlc/anomalies/detect", { method: "POST" }),
  rca: (suspect_build: string) => api("/sdlc/rca", { body: { suspect_build } }),
  builds: () => api("/sdlc/builds"),
  releases: () => api("/sdlc/releases"),
  deploy: (body: Record<string, unknown>) => api("/sdlc/releases/deploy", { body }),
  telemetry: () => api("/telemetry"),
  tokenBenchmark: () => api("/telemetry/token-benchmark"),
  governance: () => api("/governance/overview"),
  audit: () => api("/governance/audit?limit=60"),
  health: () => api("/health"),
  adminReset: () => api("/admin/demo/reset", { method: "POST" }),
  retention: () => api("/admin/retention/run", { method: "POST" }),
  users: () => api("/admin/users"),
};
