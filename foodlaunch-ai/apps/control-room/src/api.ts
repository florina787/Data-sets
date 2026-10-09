// Thin API client for the control-room backend. Sessions are server-side;
// the token only identifies the signed-in demo account.

export type User = { id: string; username: string; display_name: string; role: string };

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: Record<string, unknown> = {}) {
    super(message);
  }
}

const TOKEN_KEY = "foodlaunch.token";
const USER_KEY = "foodlaunch.user";

function read(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, value);
  } catch {
    /* storage unavailable: session lasts for this tab only */
  }
}

let token: string | null = read(TOKEN_KEY);
let listeners: Array<(u: User | null) => void> = [];

export function storedUser(): User | null {
  const raw = read(USER_KEY);
  return raw && token ? (JSON.parse(raw) as User) : null;
}

export function onAuthChange(fn: (u: User | null) => void) {
  listeners.push(fn);
  return () => {
    listeners = listeners.filter((l) => l !== fn);
  };
}

function setSession(t: string | null, user: User | null) {
  token = t;
  write(TOKEN_KEY, t);
  write(USER_KEY, user ? JSON.stringify(user) : null);
  listeners.forEach((l) => l(user));
}

export async function api<T = any>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...init, headers: { ...headers, ...(init.headers as object) } });
  const text = await response.text();
  const body = text ? JSON.parse(text) : {};
  if (!response.ok) {
    if (response.status === 401 && token) setSession(null, null); // e.g. after Reset Demo
    throw new ApiError(response.status, body.error ?? "error", body.message ?? response.statusText, body.details ?? {});
  }
  return body as T;
}

export const post = <T = any>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export async function login(username: string, password: string): Promise<User> {
  const result = await post<{ token: string; user: User }>("/api/auth/login", { username, password });
  setSession(result.token, result.user);
  return result.user;
}

export async function logout() {
  try {
    await post("/api/auth/logout");
  } finally {
    setSession(null, null);
  }
}

export async function waitForJob(jobId: string, onTick?: () => void): Promise<any> {
  // Polls a real background job; resolves only when the server reports completion.
  for (;;) {
    const job = await api(`/api/jobs/${jobId}`).catch(() => null);
    onTick?.();
    if (job && job.status !== "running") {
      if (job.status !== "succeeded") throw new ApiError(500, "job_failed", job.error ?? "Job failed", job.result ?? {});
      return job.result;
    }
    await new Promise((r) => setTimeout(r, 900));
  }
}
