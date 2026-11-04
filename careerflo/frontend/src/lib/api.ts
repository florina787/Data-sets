import { getToken, signOutLocal } from "./session";

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, detail: any) {
    super(typeof detail === "string" ? detail : detail?.message || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? "";

export async function api<T = any>(path: string, opts: RequestInit & { json?: unknown; idempotent?: string } = {}): Promise<T> {
  const headers = new Headers(opts.headers);
  const token = await getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (opts.json !== undefined) headers.set("Content-Type", "application/json");
  if (opts.idempotent) headers.set("Idempotency-Key", opts.idempotent);
  const res = await fetch(BASE + path, { ...opts, headers, body: opts.json !== undefined ? JSON.stringify(opts.json) : opts.body });
  if (res.status === 401 && token) signOutLocal();
  if (!res.ok) {
    let detail: any = res.statusText;
    try { detail = (await res.json()).detail; } catch { /* non-JSON */ }
    if (res.status === 402) window.dispatchEvent(new CustomEvent("cf:upgrade", { detail }));
    throw new ApiError(res.status, detail);
  }
  const type = res.headers.get("content-type") || "";
  return (type.includes("json") ? res.json() : (res.blob() as any)) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const blob = await api<Blob>(path);
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  a.click();
  URL.revokeObjectURL(url);
}

/** POST and read a Server-Sent-Events stream (used by the assistant). */
export async function stream(path: string, json: unknown, onEvent: (e: any) => void) {
  const token = await getToken();
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(json),
  });
  if (!res.ok || !res.body) {
    let detail: any = res.statusText;
    try { detail = (await res.json()).detail; } catch { /* ignore */ }
    if (res.status === 402) window.dispatchEvent(new CustomEvent("cf:upgrade", { detail }));
    throw new ApiError(res.status, detail);
  }
  const reader = res.body.getReader();
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
      if (chunk.startsWith("data: ")) onEvent(JSON.parse(chunk.slice(6)));
    }
  }
}
