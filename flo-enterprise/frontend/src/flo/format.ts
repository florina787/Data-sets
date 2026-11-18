// Formatting for contract values. Percent-unit values are fractions (0.2785 = 27.85%); bps values are basis points.
const ISO_DAY = /^\d{4}-\d{2}-\d{2}$/;

export function compactNumber(v: number): string {
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}bn`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}m`;
  if (a >= 1e4) return `${(v / 1e3).toFixed(0)}k`;
  return v.toLocaleString("en-CA", { maximumFractionDigits: 2 });
}

export function formatValue(v: number | null | undefined, unit: string, opts: { compact?: boolean } = {}): string {
  if (v == null || Number.isNaN(v)) return "—";
  switch (unit) {
    case "CAD":
      return opts.compact === false ? `CAD ${v.toLocaleString("en-CA", { maximumFractionDigits: 0 })}` : `CAD ${compactNumber(v)}`;
    case "%":
      return `${(v * 100).toFixed(Math.abs(v) < 0.1 ? 2 : 1)}%`;
    case "bps":
      return `${v.toFixed(1)} bps`;
    case "x":
      return `${v.toFixed(2)}x`;
    case "ratio":
      return v.toFixed(2);
    case "count":
    case "score":
      return Math.round(v).toLocaleString("en-CA");
    case "years":
      return `${v.toFixed(1)} yrs`;
    default:
      return compactNumber(v);
  }
}

export function formatDelta(d: number | null | undefined, unit: string): string {
  if (d == null) return "";
  const sign = d > 0 ? "+" : d < 0 ? "−" : "";
  const a = Math.abs(d);
  switch (unit) {
    case "%":
      return `${sign}${(a * 100).toFixed(2)}%`;
    case "pp":
      return `${sign}${(a * 100).toFixed(2)} pp`;
    case "bps":
      return `${sign}${a.toFixed(1)} bps`;
    case "CAD":
      return `${sign}CAD ${compactNumber(a)}`;
    default:
      return `${sign}${compactNumber(a)}`;
  }
}

export function categoryLabel(c: string): string {
  if (ISO_DAY.test(c)) return new Date(`${c}T00:00:00`).toLocaleDateString("en-CA", { month: "short", year: "2-digit" });
  return c;
}

export const PROVENANCE_LABEL: Record<string, string> = {
  platform_synthetic: "Synthetic platform data",
  user_supplied: "You provided",
  calculated_from_user_inputs: "Calculated from your inputs",
  illustrative_assumption: "Illustrative assumption",
  workflow_trace: "Workflow trace",
};

export const STATUS_LABEL: Record<string, string> = {
  complete: "Complete", partial: "Partial — some data withheld", denied: "Not authorized", needs_input: "Needs your input",
  rejected: "Rejected by input guard", cancelled: "Cancelled", error: "Error",
};

export const prefersReducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
