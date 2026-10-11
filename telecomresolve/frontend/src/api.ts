const TOKEN_KEY = "tr.demo.token";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

let token: string | null = null;
try { token = sessionStorage.getItem(TOKEN_KEY); } catch { token = null; }

export function setToken(t: string | null) {
  token = t;
  try { if (t) sessionStorage.setItem(TOKEN_KEY, t); else sessionStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}
export function getToken() { return token; }

export async function api<T>(path: string, init: RequestInit & { idempotencyKey?: string } = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init.idempotencyKey) headers["Idempotency-Key"] = init.idempotencyKey;
  const res = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as Record<string, string>) } });
  const text = await res.text();
  const body = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const d = body?.detail ?? {};
    const message = typeof d === "string" ? d : d.message ?? d.code ?? res.statusText;
    throw new ApiError(res.status, typeof d === "object" ? d.code ?? "ERROR" : "ERROR", message);
  }
  return body as T;
}

export const post = <T,>(path: string, body?: unknown, opts: { idempotencyKey?: string } = {}) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), ...opts });

export const enc = (s: string) => encodeURIComponent(s);
