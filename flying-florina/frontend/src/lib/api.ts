import type { Envelope } from "./types";
import { useSession } from "./store";

export class ApiError extends Error {
  status: number;
  code: string;
  details: unknown;
  requestId?: string;
  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

function headers(json = true): Record<string, string> {
  const h: Record<string, string> = {};
  const token = useSession.getState().token;
  if (token) h.Authorization = `Bearer ${token}`;
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function handle<T>(res: Response): Promise<Envelope<T>> {
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiError(res.status, "bad_response", text.slice(0, 200));
  }
  if (!res.ok) {
    const b = (body ?? {}) as { code?: string; message?: string; details?: unknown; request_id?: string };
    if (res.status === 401) useSession.getState().expire();
    throw new ApiError(res.status, b.code ?? "error", b.message ?? res.statusText, b.details, b.request_id);
  }
  return body as Envelope<T>;
}

export async function get<T>(path: string): Promise<Envelope<T>> {
  return handle<T>(await fetch(path, { headers: headers(false) }));
}

export async function post<T>(path: string, body?: unknown): Promise<Envelope<T>> {
  return handle<T>(await fetch(path, { method: "POST", headers: headers(), body: body === undefined ? "{}" : JSON.stringify(body) }));
}

export async function upload<T>(path: string, file: File): Promise<Envelope<T>> {
  const fd = new FormData();
  fd.append("file", file);
  return handle<T>(await fetch(path, { method: "POST", headers: headers(false), body: fd }));
}

/** Download an authenticated file (reports, bundles, audit export) without exposing the token in a URL. */
export async function download(path: string, fallbackName: string): Promise<void> {
  const res = await fetch(path, { headers: headers(false) });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      msg = (await res.json()).message ?? msg;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, "download_failed", msg);
  }
  const blob = await res.blob();
  const cd = res.headers.get("content-disposition") ?? "";
  const name = /filename="?([^";]+)"?/.exec(cd)?.[1] ?? fallbackName;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
