// Thin API client. The bearer token is a local demo token held in sessionStorage; no secrets
// (model keys, storage credentials) ever reach the browser.
import type {
  ApiErrorBody, AppConfig, GridWindow, Message, Operation, Profile, Run, User, Version, Workbook,
} from "./types";

const TOKEN_KEY = "flopilot.token";

export class ApiError extends Error {
  status: number;
  code: string;
  retryable: boolean;
  details?: Record<string, unknown>;
  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.status = status;
    this.code = body.code;
    this.retryable = !!body.retryable;
    this.details = body.details;
  }
}

export const auth = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (t: string) => sessionStorage.setItem(TOKEN_KEY, t),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = auth.get();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, { code: "network_error", message: "FloPilot's server could not be reached. Check that it is running.", retryable: true });
  }
  if (!res.ok) {
    let body: ApiErrorBody;
    try {
      body = await res.json();
    } catch {
      body = { code: "http_error", message: `Request failed (${res.status}).` };
    }
    throw new ApiError(res.status, body);
  }
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

const post = <T>(path: string, body?: unknown, headers?: Record<string, string>) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), headers });

export const api = {
  config: () => request<AppConfig>("/config"),
  demoLogin: (user: string) => post<{ token: string; user: User }>("/auth/demo-login", { user }),
  me: () => request<User>("/me"),
  workbooks: () => request<Workbook[]>("/workbooks"),
  loadDemo: () => post<Workbook>("/workbooks/demo"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Workbook>("/workbooks", { method: "POST", body: form });
  },
  workbook: (id: string) => request<Workbook>(`/workbooks/${id}`),
  deleteWorkbook: (id: string) => request<{ deleted: boolean }>(`/workbooks/${id}`, { method: "DELETE" }),
  profile: (id: string, version?: number) => request<Profile>(`/workbooks/${id}/profile${version ? `?version=${version}` : ""}`),
  cells: (id: string, sheet: string, version: number, r0: number, r1: number, c0 = 1, c1 = 120) =>
    request<GridWindow>(`/workbooks/${id}/sheets/${encodeURIComponent(sheet)}/cells?version=${version}&r0=${r0}&r1=${r1}&c0=${c0}&c1=${c1}`),
  find: (id: string, sheet: string, version: number, q: string) =>
    request<{ match_count: number; truncated: boolean; rows: GridWindow["rows"] }>(`/workbooks/${id}/sheets/${encodeURIComponent(sheet)}/find?version=${version}&q=${encodeURIComponent(q)}`),
  versions: (id: string) => request<Version[]>(`/workbooks/${id}/versions`),
  chat: (id: string, message: string, conversationId: string | null, selection: { sheet?: string; cell?: string; range?: string } | null) =>
    post<{ run_id: string; conversation_id: string }>(`/workbooks/${id}/chat`, { message, conversation_id: conversationId, selection }),
  run: (runId: string) => request<Run>(`/runs/${runId}`),
  cancelRun: (runId: string) => post<{ state: string }>(`/runs/${runId}/cancel`),
  runs: (id: string) => request<any[]>(`/workbooks/${id}/runs`),
  conversations: (id: string) => request<{ id: string; title: string; updated_at: string }[]>(`/workbooks/${id}/conversations`),
  messages: (conversationId: string) => request<Message[]>(`/conversations/${conversationId}/messages`),
  operations: (id: string) => request<Operation[]>(`/workbooks/${id}/operations`),
  operation: (opId: string) => request<Operation>(`/operations/${opId}`),
  approve: (op: Operation, acknowledgeRisks: boolean, idempotencyKey: string) =>
    post<Operation>(`/operations/${op.id}/approve`, {
      expected_version: op.base_version, change_set_hash: op.change_set_hash, acknowledge_risks: acknowledgeRisks,
    }, { "Idempotency-Key": idempotencyKey }),
  reject: (opId: string) => post<Operation>(`/operations/${opId}/reject`),
  refresh: (opId: string) => post<any>(`/operations/${opId}/refresh`),
  restore: (id: string, version: number) => post<any>(`/workbooks/${id}/restore`, { version }),
  activity: (id: string) => request<{ events: any[] }>(`/workbooks/${id}/activity`),
  downloadUrl: (id: string, version: number, format: "xlsx" | "csv" = "xlsx", sheet?: string) =>
    `/api/workbooks/${id}/versions/${version}/download?format=${format}${sheet ? `&sheet=${encodeURIComponent(sheet)}` : ""}`,
  summary: (id: string, conversationId: string | null) =>
    request<string>(`/workbooks/${id}/analysis-summary${conversationId ? `?conversation_id=${conversationId}` : ""}`),
};

/** Download through fetch so the Authorization header is sent (no tokens in URLs). */
export async function download(url: string, fallbackName: string): Promise<void> {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${auth.get() ?? ""}` } });
  if (!res.ok) {
    let body: ApiErrorBody = { code: "download_failed", message: "Download failed." };
    try { body = await res.json(); } catch { /* not json */ }
    throw new ApiError(res.status, body);
  }
  const blob = await res.blob();
  const disposition = res.headers.get("content-disposition") ?? "";
  const match = /filename\*=UTF-8''([^;]+)/.exec(disposition);
  const name = match ? decodeURIComponent(match[1]) : fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

export function saveText(text: string, name: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/markdown" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
