export const cad = (v: number | string | null | undefined, digits = 0) =>
  v == null ? "—" : `CAD ${Number(v).toLocaleString("en-CA", { maximumFractionDigits: digits, minimumFractionDigits: digits })}`;
export const bn = (v: number | string | null | undefined) => (v == null ? "—" : `CAD ${(Number(v) / 1e9).toFixed(2)}bn`);
export const mn = (v: number | string | null | undefined) => (v == null ? "—" : `CAD ${(Number(v) / 1e6).toFixed(1)}m`);
export const compact = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}bn`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}m`;
  if (a >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
  return v.toFixed(0);
};
export const pct = (v: number | null | undefined, d = 2) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
export const num = (v: number | null | undefined, d = 2) => (v == null ? "—" : v.toFixed(d));
export const month = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-CA", { month: "short", year: "2-digit" });
export const human = (s: string) => s.replace(/_/g, " ").replace(/^expense /, "").replace(/\b\w/g, (c) => c.toUpperCase());
