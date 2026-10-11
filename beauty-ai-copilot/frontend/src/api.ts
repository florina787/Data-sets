// Thin API client. The persona header only selects which seeded demo user the session acts as;
// every permission decision is enforced by the backend.

export class ApiError extends Error {
  constructor(public status: number, public category: string, public code: string, message: string,
              public details: Record<string, unknown> = {}, public traceId?: string) {
    super(message);
  }
}

let persona = (() => {
  try { return localStorage.getItem("persona") ?? "u-po"; } catch { return "u-po"; }
})();

export function getPersona(): string { return persona; }
export function setPersona(p: string) {
  persona = p;
  try { localStorage.setItem("persona", p); } catch { /* storage unavailable */ }
}

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  const res = await fetch(path, {
    method: opts.method ?? "GET",
    headers: { "Content-Type": "application/json", "X-Demo-User": persona, ...(opts.headers ?? {}) },
    body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
  });
  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;
  if (!res.ok) {
    const e = (data && data.error) || {};
    throw new ApiError(res.status, e.category ?? "error", e.code ?? String(res.status), e.message ?? res.statusText, e.details ?? {}, e.trace_id);
  }
  return data as T;
}

export function idempotencyKey(): string {
  return (globalThis.crypto?.randomUUID?.() ?? `k-${Date.now()}-${Math.random().toString(16).slice(2)}`);
}
