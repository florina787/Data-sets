// Browser-local storage. Two separate namespaces:
//   femora:v1:    her real, private records
//   femora:demo:  the interactive demo's synthetic data (never mixed with real records)
// The mode is chosen per browser tab (sessionStorage) and fixed for the page's lifetime.
export const REAL_PREFIX = "femora:v1:";
export const DEMO_PREFIX = "femora:demo:";
const MODE_KEY = "femora:mode";

export function isDemo(): boolean {
  try { return sessionStorage.getItem(MODE_KEY) === "demo"; } catch { return false; }
}
export const prefix = () => (isDemo() ? DEMO_PREFIX : REAL_PREFIX);
export function setDemoMode(on: boolean) {
  try { if (on) sessionStorage.setItem(MODE_KEY, "demo"); else sessionStorage.removeItem(MODE_KEY); } catch { /* ignore */ }
}

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(prefix() + key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function save<T>(key: string, value: T): void {
  try {
    localStorage.setItem(prefix() + key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: keeps working in memory */
  }
}

/** Deletes every key in the current namespace (real records, or the demo's synthetic data). */
export function resetDemo(): void {
  const p = prefix();
  Object.keys(localStorage).filter((k) => k.startsWith(p)).forEach((k) => localStorage.removeItem(k));
}
export const clearNamespace = (p: string) => Object.keys(localStorage).filter((k) => k.startsWith(p)).forEach((k) => localStorage.removeItem(k));

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
export const dayKey = (d: Date) => d.toISOString().slice(0, 10);
export const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
