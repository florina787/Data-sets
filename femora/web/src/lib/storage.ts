// Browser-local demo state. Versioned keys so schema changes never crash old state; one call resets everything.
// Production will replace this with encrypted local storage + consented sync (see docs/AUDIT.md §10).
const PREFIX = "femora:v1:";

export function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(PREFIX + key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function save<T>(key: string, value: T): void {
  try {
    localStorage.setItem(PREFIX + key, JSON.stringify(value));
  } catch {
    /* storage full or blocked: demo keeps working in memory */
  }
}

export function resetDemo(): void {
  Object.keys(localStorage).filter((k) => k.startsWith(PREFIX)).forEach((k) => localStorage.removeItem(k));
}

export const uid = () => Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
export const dayKey = (d: Date) => d.toISOString().slice(0, 10);
export const addDays = (d: Date, n: number) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
