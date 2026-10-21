// Typed API client. All requests go to the same-origin /api proxy; no secrets live in the frontend.
export type Filters = {
  topics?: string[];
  resolution?: string[];
  sentiment_end?: string[];
  escalation?: string[];
  handoff?: string[];
  brands?: string[];
  languages?: string[];
  date_from?: string;
  date_to?: string;
  conversation_keys?: string[];
};

export type Dataset = {
  id: string; name: string; kind: string; synthetic: boolean; status: string; source: string;
  active_analysis: string; imported_at: string | null; conversations: number | null; eligible: number | null;
  requested: number | null; data_from?: string | null; data_to?: string | null;
};

export type BreakdownItem = { key: string; label: string; count: number; share: number | null; evidence_ids: string[] };
export type Evidence = { id: string; conversation_key: string; message_id: string; quote: string; supports?: string; role?: string; language?: string; ref?: string; valid?: boolean; translated?: boolean };
export type Breakdown = {
  dataset: { id: string; name: string; synthetic: boolean; analysis: string }; filters: Filters; scope: string; field: string;
  denominator: number; unit: string; unknown: number; items: BreakdownItem[]; evidence: Evidence[]; evidence_ids: string[];
};
export type CrossTab = {
  scope: string; denominator: number; columns: { key: string; label: string }[];
  rows: { key: string; label: string; total: number; cells: { key: string; label: string; count: number; share_of_row: number | null }[] }[];
};

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export function filtersParam(f: Filters | undefined): string | undefined {
  if (!f) return undefined;
  const clean = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== undefined && v !== null && !(Array.isArray(v) && v.length === 0) && v !== ""));
  return Object.keys(clean).length ? JSON.stringify(clean) : undefined;
}

export async function api<T>(path: string, opts: { method?: string; body?: unknown; params?: Record<string, string | number | undefined>; headers?: Record<string, string>; form?: FormData } = {}): Promise<T> {
  const url = new URL(path.startsWith("/") ? path : `/api/${path}`, window.location.origin);
  for (const [k, v] of Object.entries(opts.params ?? {})) if (v !== undefined && v !== "") url.searchParams.set(k, String(v));
  const init: RequestInit = { method: opts.method ?? (opts.body || opts.form ? "POST" : "GET"), headers: { ...(opts.headers ?? {}) } };
  if (opts.form) init.body = opts.form;
  else if (opts.body !== undefined) {
    init.body = JSON.stringify(opts.body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  for (let attempt = 0; ; attempt++) {
    try {
      res = await fetch(url.toString(), init);
      break;
    } catch (e) {
      if (attempt >= 1 || init.method !== "GET") throw new ApiError(0, "Cannot reach the ConvoLens backend. Is it running?");
      await new Promise((r) => setTimeout(r, 600));
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { const j = await res.json(); detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* not json */ }
    throw new ApiError(res.status, detail);
  }
  const ct = res.headers.get("content-type") ?? "";
  return (ct.includes("application/json") ? res.json() : res.text()) as Promise<T>;
}

export function dsPath(datasetId: string, rest: string) {
  return `/api/datasets/${encodeURIComponent(datasetId)}/${rest}`;
}

// ---------------------------------------------------------------- Flo session + SSE streaming
type Session = { session_id: string; session_token: string };
let sessionPromise: Promise<Session> | null = null;

export function getSession(): Promise<Session> {
  if (!sessionPromise) {
    sessionPromise = (async () => {
      try {
        const cached = sessionStorage.getItem("convolens.flo.session");
        if (cached) return JSON.parse(cached) as Session;
      } catch { /* storage unavailable */ }
      const s = await api<Session>("/api/flo/sessions", { method: "POST" });
      try { sessionStorage.setItem("convolens.flo.session", JSON.stringify(s)); } catch { /* ignore */ }
      return s;
    })();
  }
  return sessionPromise;
}

export async function sessionHeaders(): Promise<Record<string, string>> {
  const s = await getSession();
  return { "X-Flo-Session": s.session_id, "X-Flo-Token": s.session_token };
}

export function resetSession() {
  sessionPromise = null;
  try { sessionStorage.removeItem("convolens.flo.session"); } catch { /* ignore */ }
}

export type FloEvent = { type: string; [k: string]: any };

export async function streamSSE(path: string, body: unknown, onEvent: (e: FloEvent) => void, signal: AbortSignal): Promise<void> {
  let headers = await sessionHeaders();
  let res = await fetch(path, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  if (res.status === 403) { // stale session (e.g. backend database reset): start a new one once
    resetSession();
    headers = await sessionHeaders();
    res = await fetch(path, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail; } catch { /* ignore */ }
    throw new ApiError(res.status, detail);
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (line.startsWith("data: ")) {
          try { onEvent(JSON.parse(line.slice(6))); } catch { /* ignore malformed */ }
        }
      }
    }
  }
}
