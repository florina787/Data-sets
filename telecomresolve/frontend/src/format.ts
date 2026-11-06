export const STATUS_LABEL: Record<string, string> = {
  NEW: "New", TRIAGED: "Triaged", COLLECTING_EVIDENCE: "Collecting evidence", ASSESSING: "Assessing",
  RECOMMENDATION_READY: "Recommendation ready", AWAITING_APPROVAL: "Pending approval", APPROVED: "Approved",
  EXECUTING: "Executing", VERIFYING: "Recovery not yet verified", RESOLVED: "Resolved (recovery verified)",
  MONITORING: "Monitoring — recovery not yet verified", ESCALATED: "Escalated", NEEDS_INFORMATION: "Insufficient evidence",
  REJECTED: "Rejected", CANCELLED: "Cancelled", FAILED: "Failed",
};

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral";
export function statusTone(s: string): Tone {
  if (s === "RESOLVED") return "ok";
  if (["ESCALATED", "FAILED", "REJECTED"].includes(s)) return "bad";
  if (["AWAITING_APPROVAL", "NEEDS_INFORMATION", "MONITORING", "VERIFYING"].includes(s)) return "warn";
  if (["CANCELLED", "NEW"].includes(s)) return "neutral";
  return "info";
}
export const TONE_ICON: Record<Tone, string> = { ok: "✓", warn: "!", bad: "✕", info: "•", neutral: "○" };

export const ACTION_LABEL: Record<string, string> = {
  create_technician_dispatch: "Create technician dispatch (simulated)",
  associate_case_with_incident: "Associate case with incident",
  suggest_customer_troubleshooting: "Suggest customer troubleshooting",
  draft_customer_update: "Draft customer update (never sent)",
  reset_equipment: "Reset equipment (proposal only)",
  modify_service: "Modify service (proposal only)",
  apply_bill_credit: "Apply bill credit (disabled)",
};

export const CATEGORY_LABEL: Record<string, string> = {
  AREA_INCIDENT: "Area incident on mapped path", LINE_IMPAIRMENT: "Access line impairment",
  EQUIPMENT_FAULT: "Customer equipment fault", HOME_NETWORK: "Home network / Wi-Fi",
  UNDECLARED_AREA_ISSUE: "Shared issue, no declared incident", INSUFFICIENT_EVIDENCE: "Insufficient evidence",
  CONTRADICTORY_EVIDENCE: "Contradictory evidence",
};

export function fmtTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
export const human = (s: string) => s.replace(/_/g, " ");
