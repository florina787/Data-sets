import { useCallback, useEffect, useRef, useState } from "react";
import { identity } from "./store";

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

function qs(params?: Record<string, string | number | undefined | null>) {
  if (!params) return "";
  const p = Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "");
  return p.length ? "?" + new URLSearchParams(p.map(([k, v]) => [k, String(v)])).toString() : "";
}

export function headers(extra?: Record<string, string>) {
  return { "Content-Type": "application/json", "X-Role": identity.role, "X-User": identity.user, ...extra };
}

export async function api<T = any>(path: string, opts: { method?: string; params?: Record<string, any>; body?: unknown } = {}): Promise<T> {
  const r = await fetch(`/api${path}${qs(opts.params)}`, { method: opts.method ?? "GET", headers: headers(), body: opts.body === undefined ? undefined : JSON.stringify(opts.body) });
  if (!r.ok) {
    let msg = r.statusText;
    try { msg = (await r.json()).detail ?? msg; } catch { /* not json */ }
    throw new ApiError(r.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  const ct = r.headers.get("content-type") ?? "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export function reportUrl(params: Record<string, string>) { return `/api/reports/executive${qs(params)}`; }

/** Small data hook: refetches when the key changes, optional polling. */
export function useApi<T = any>(path: string | null, params?: Record<string, any>, pollMs?: number) {
  const key = path ? path + qs(params) : null;
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!key);
  const keyRef = useRef(key);
  keyRef.current = key;
  const load = useCallback(async (silent = false) => {
    if (!key || !path) return;
    if (!silent) setLoading(true);
    try {
      const d = await api<T>(path, { params });
      if (keyRef.current === key) { setData(d); setError(null); }
    } catch (e: any) {
      if (keyRef.current === key) setError(e.message ?? String(e));
    } finally {
      if (keyRef.current === key) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!pollMs || !key) return;
    const t = setInterval(() => load(true), pollMs);
    return () => clearInterval(t);
  }, [pollMs, key, load]);
  return { data, error, loading, reload: () => load(true) };
}

export interface SseHandlers { activity?: (a: any) => void; delta?: (t: string) => void; final?: (p: any) => void }

export async function chatStream(body: unknown, h: SseHandlers): Promise<void> {
  const r = await fetch("/api/chat/stream", { method: "POST", headers: headers(), body: JSON.stringify(body) });
  if (!r.ok || !r.body) throw new ApiError(r.status, (await r.text()) || r.statusText);
  const reader = r.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const ev = /event: (\w+)/.exec(chunk)?.[1];
      const data = /data: (.*)/s.exec(chunk)?.[1];
      if (!ev || data === undefined) continue;
      const parsed = JSON.parse(data);
      if (ev === "activity") h.activity?.(parsed);
      else if (ev === "delta") h.delta?.(parsed);
      else if (ev === "final") h.final?.(parsed);
    }
  }
}
