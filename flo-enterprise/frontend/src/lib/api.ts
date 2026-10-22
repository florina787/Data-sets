// Typed fetch wrapper. The bearer token is kept in sessionStorage (demo mock IdP); production uses the enterprise IdP
// with httpOnly cookies / PKCE. No token mappings, client PII vault data or secrets are ever stored client-side.
export class ApiError extends Error {
  status: number;
  code?: string;
  denials?: string[];
  constructor(status: number, detail: unknown) {
    const d = (detail ?? {}) as { code?: string; message?: string; denials?: string[] };
    super(typeof detail === "string" ? detail : d.message || d.code || `HTTP ${status}`);
    this.status = status;
    this.code = d.code;
    this.denials = d.denials;
  }
}

const KEY = "flo.token";
export const tokenStore = {
  get: () => sessionStorage.getItem(KEY),
  set: (t: string) => sessionStorage.setItem(KEY, t),
  clear: () => sessionStorage.removeItem(KEY),
};

export async function api<T = any>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers: Record<string, string> = { ...(init.headers as Record<string, string>) };
  const t = tokenStore.get();
  if (t) headers.Authorization = `Bearer ${t}`;
  let body = init.body;
  if (init.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.json);
  }
  const r = await fetch(path, { ...init, headers, body });
  if (r.status === 401) {
    tokenStore.clear();
    window.dispatchEvent(new Event("flo:logout"));
  }
  if (!r.ok) {
    let detail: unknown = r.statusText;
    try {
      detail = (await r.json()).detail;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(r.status, detail);
  }
  const ct = r.headers.get("content-type") || "";
  return (ct.includes("json") ? r.json() : r.text()) as Promise<T>;
}

export async function download(path: string, filename: string) {
  const r = await fetch(path, { headers: { Authorization: `Bearer ${tokenStore.get()}` } });
  if (!r.ok) throw new ApiError(r.status, (await r.json().catch(() => ({}))).detail);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export type Lineage = {
  metrics: { id: string; name: string; definition: string; formula: string; unit: string; owner: string; version: string }[];
  sources: { system: string; category: string; mode: string; connected_to_production: boolean; freshness: string }[];
  methodology: string;
  as_of: string;
  refreshed_at: string;
  dataset_version: string;
  semantic_layer_version: string;
  synthetic: boolean;
};
export type WithLineage<T> = { data: T; lineage: Lineage };
