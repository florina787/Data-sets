export const pct = (x: number | null | undefined, d = 2) =>
  x == null || !Number.isFinite(x) ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;
export const pctPlain = (x: number | null | undefined, d = 1) =>
  x == null || !Number.isFinite(x) ? "—" : `${(x * 100).toFixed(d)}%`;
export const num = (x: number | null | undefined, d = 2) =>
  x == null || !Number.isFinite(x) ? "—" : x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
export const int = (x: number | null | undefined) => (x == null ? "—" : Math.round(x).toLocaleString("en-US"));
export const dateShort = (s: string) => s.slice(0, 10);
/** Two-character badge. Letter-only tickers use their first two letters; tickers with digits use letter + last digit(s). */
export const monogram = (t: string) => {
  const u = t.toUpperCase();
  const digits = u.replace(/\D/g, "");
  if (digits) return (u[0] + digits.slice(-2)).slice(0, 3);
  return u.replace(/[^A-Z]/g, "").slice(0, 2) || u.slice(0, 2);
};
export const tone = (x: number | null | undefined) => (x == null ? "" : x > 0 ? "up" : x < 0 ? "down" : "");
