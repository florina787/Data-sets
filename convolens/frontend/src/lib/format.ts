export const fmtInt = (n: number | null | undefined) => (n === null || n === undefined ? "–" : n.toLocaleString("en-US"));
export const fmtPct = (n: number | null | undefined, digits = 0) => (n === null || n === undefined ? "–" : `${(n * 100).toFixed(digits)}%`);
export const ratio = (num: number, den: number) => (den ? `${fmtInt(num)} of ${fmtInt(den)} (${fmtPct(num / den)})` : `${fmtInt(num)} of 0`);
export function fmtDate(iso: string | null | undefined, opts: Intl.DateTimeFormatOptions = { year: "numeric", month: "short", day: "numeric" }) {
  if (!iso) return "–";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "–" : d.toLocaleString("en-GB", opts);
}
export const titleCase = (s: string) => s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
