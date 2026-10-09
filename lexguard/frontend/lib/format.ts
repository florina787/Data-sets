export const pct = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "-" : `${(v * 100).toFixed(digits)}%`;

export const num = (v: number | null | undefined, digits = 0) =>
  v === null || v === undefined ? "-" : v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });

export const usd = (v: number | null | undefined) =>
  v === null || v === undefined ? "-" : v.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export const humanize = (s: string | null | undefined) =>
  !s ? "" : s.replace(/_/g, " ").toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase()).replace(/\b(Ai|Rag|Llm|Dd|Hitl)\b/g, (w) => w.toUpperCase());

export type Tone = "good" | "warn" | "bad" | "info" | "neutral";

export function statusTone(status: string | null | undefined): Tone {
  switch (status) {
    case "COMPLETED": case "PASS": case "SUPPORTED": case "ALIGNED": case "APPROVED": case "PERMITTED": case "VERIFIED":
    case "IMPLEMENTED": case "ok":
      return "good";
    case "REVIEW_REQUIRED": case "PERMITTED_WITH_CONTROLS": case "PARTIALLY_SUPPORTED": case "DEVIATION": case "RESTRICTED":
    case "NEEDS_REVIEW": case "PENDING_REVIEW": case "PARTIAL": case "NEEDS_INPUT": case "warn": case "pending": case "MEDIUM":
    case "HUMAN_DECISION_REQUIRED":
      return "warn";
    case "BLOCKED": case "ACCESS_DENIED": case "PROHIBITED": case "UNSUPPORTED": case "SOURCE_NOT_FOUND": case "ESCALATION_REQUIRED":
    case "FAIL": case "REJECTED": case "HALTED": case "ERROR": case "blocked": case "error": case "HIGH": case "CRITICAL":
      return "bad";
    case "PLANNED": case "LOW":
      return "info";
    default:
      return "neutral";
  }
}

/** Split text around a highlight (case-insensitive) for evidence rendering. */
export function splitHighlight(text: string, highlight?: string | null): { before: string; match: string; after: string } {
  if (!highlight) return { before: text, match: "", after: "" };
  const i = text.toLowerCase().indexOf(highlight.toLowerCase());
  if (i < 0) return { before: text, match: "", after: "" };
  return { before: text.slice(0, i), match: text.slice(i, i + highlight.length), after: text.slice(i + highlight.length) };
}
