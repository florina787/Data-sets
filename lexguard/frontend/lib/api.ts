import type { AuditEvent, CopilotResponse, MatterDetail, MatterSummary, User } from "@/types/api";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public status: number, public code: string | undefined, message: string) { super(message); }
}

async function request<T>(path: string, userId: string | null, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(userId ? { "X-LexGuard-User": userId } : {}), ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, "UNREACHABLE", `Cannot reach the LexGuard API at ${API_URL}. Is the backend running?`);
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const d = body?.detail;
    const message = typeof d === "string" ? d : d?.message || "Request failed.";
    throw new ApiError(res.status, typeof d === "object" ? d?.code : undefined, message);
  }
  return body as T;
}

export const api = {
  get: <T,>(path: string, userId: string | null) => request<T>(path, userId),
  post: <T,>(path: string, userId: string | null, body: unknown) =>
    request<T>(path, userId, { method: "POST", body: JSON.stringify(body) }),
  health: () => request<{ status: string; demo_mode: boolean; paid_llm_calls: number }>("/health", null),
  users: () => request<User[]>("/users", null),
  matters: (u: string) => request<MatterSummary[]>("/matters", u),
  matter: (u: string, id: string) => request<MatterDetail>(`/matters/${id}`, u),
  chat: (u: string, matterId: string, message: string, selectedFindingId?: string | null) =>
    request<CopilotResponse>("/copilot/chat", u, { method: "POST", body: JSON.stringify({
      matter_id: matterId, message, ...(selectedFindingId ? { selected_finding_id: selectedFindingId } : {}) }) }),
  approve: (u: string, wp: string, destination: string, comment: string) =>
    request<any>("/review/approve", u, { method: "POST", body: JSON.stringify({ work_product_id: wp, destination, comment }) }),
  reject: (u: string, wp: string, comment: string) =>
    request<any>("/review/reject", u, { method: "POST", body: JSON.stringify({ work_product_id: wp, comment }) }),
  trace: (u: string, requestId: string) => request<{ request_id: string; chain: AuditEvent[] }>(`/audit/trace/${requestId}`, u),
};
