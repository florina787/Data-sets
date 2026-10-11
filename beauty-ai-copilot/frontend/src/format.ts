export const pp = (v: number | null | undefined, digits = 2) =>
  v === null || v === undefined ? "—" : `${v > 0 ? "+" : ""}${v.toFixed(digits)} pp`;

export const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : `${v.toFixed(2)}%`);

export const ci = (c: [number, number] | number[] | null | undefined) =>
  !c || c[0] === null || c[0] === undefined ? "—" : `${c[0] > 0 ? "+" : ""}${c[0].toFixed(2)} to ${c[1] > 0 ? "+" : ""}${c[1].toFixed(2)}`;

export const shortDigest = (d?: string | null) => (d ? `${d.slice(0, 15)}…${d.slice(-6)}` : "—");

export const when = (iso?: string | null) => (iso ? new Date(iso).toLocaleString() : "—");

export function statusTone(s: string | null | undefined): "pass" | "fail" | "warn" | "info" | "neutral" {
  if (!s) return "neutral";
  if (["PASS", "APPROVE", "APPROVED", "EXECUTED", "SUCCEEDED", "VALID", "RELEASED", "OK", "READY_FOR_AUTHORIZATION", "RESOLVED"].includes(s)) return "pass";
  if (["FAIL", "REJECT", "REJECTED", "FAILED", "EVALUATION_FAILED", "BLOCKED", "OPEN", "ROLLBACK_RECOMMENDED", "UNRESOLVED", "INJECTION_IGNORED", "ERROR", "STALE"].includes(s)) return "fail";
  if (["INCONCLUSIVE", "EVALUATION_INCONCLUSIVE", "PENDING", "QUEUED", "RUNNING", "OUTDATED", "NOT_APPROVED", "NEEDS_CLARIFICATION", "REVIEW_REQUIRED", "INVESTIGATED", "REQUESTED", "CANARY", "MONITORING"].includes(s)) return "warn";
  return "info";
}

// Non-colour cue for each tone (status never relies on colour alone).
export const toneIcon: Record<string, string> = { pass: "✓", fail: "✕", warn: "!", info: "•", neutral: "·" };
