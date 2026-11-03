export const SYMBOL: Record<string, string> = { USD: "$", INR: "₹", CAD: "C$" };

export function money(v: number | null | undefined, cur = "USD", compact = true): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  const s = SYMBOL[cur] ?? "";
  const a = Math.abs(v);
  let t: string;
  if (!compact) t = a.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  else if (a >= 1e9) t = `${(a / 1e9).toFixed(2)}B`;
  else if (a >= 1e6) t = `${(a / 1e6).toFixed(2)}M`;
  else if (a >= 1e4) t = `${(a / 1e3).toFixed(1)}K`;
  else t = a.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return `${v < 0 ? "−" : ""}${s}${t}`;
}

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function compact(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
}

export function pctChange(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v > 0 ? "+" : ""}${v.toFixed(1)}%`;
}

export function monthLabel(m: string) {
  const [y, mm] = m.split("-").map(Number);
  return new Date(Date.UTC(y, mm - 1, 1)).toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

export function lastMonths(end: string, n: number): string[] {
  let [y, m] = end.split("-").map(Number);
  const out: string[] = [];
  for (let i = 0; i < n; i++) { out.push(`${y}-${String(m).padStart(2, "0")}`); m -= 1; if (m === 0) { y -= 1; m = 12; } }
  return out;
}

export const AGENT_COLORS = ["#13795B", "#B8913A", "#2F6FAB", "#8E5BB5", "#D06A3A", "#3BA3A3", "#7C8C99", "#B4413C", "#5E8C31", "#C2577F", "#4C5BA8", "#A68A1F", "#2BB673", "#6B4F3A", "#0B3D2E"];
export const CAT_COLOR: Record<string, string> = {
  llm_inference: "#0B3D2E", compute: "#13795B", azure_infrastructure: "#2F6FAB", storage: "#8E5BB5", networking: "#3BA3A3", monitoring: "#7C8C99",
  third_party_tools: "#5E8C31", human_review: "#B8913A", maintenance: "#D06A3A", implementation_allocated: "#B4413C",
};
export const shortAgent = (l: string) => l.replace(" Agent", "").replace("Independent ", "");
/** Insert <br> so long axis labels wrap instead of colliding. */
export function wrap(s: string, width = 14): string {
  const words = s.split(" "); const lines: string[] = []; let cur = "";
  for (const w of words) { if ((cur + " " + w).trim().length > width && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim(); }
  if (cur) lines.push(cur);
  return lines.join("<br>");
}
export const SERIES = { revenue: "#13795B", opex: "#8FA3AE", ai: "#B8913A", aiTotal: "#D9B868", profit: "#0B3D2E", savings: "#2BB673", cost: "#B4413C", local: "#13795B", paid: "#B8913A", cached: "#8FA3AE" };
