// Pure helpers shared by components (unit-tested in src/__tests__).

export function colLetter(index: number): string {
  let n = index;
  let s = "";
  while (n > 0) {
    const m = (n - 1) % 26;
    s = String.fromCharCode(65 + m) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}

export function colIndex(letters: string): number {
  return letters.toUpperCase().split("").reduce((acc, ch) => acc * 26 + (ch.charCodeAt(0) - 64), 0);
}

export function parseCell(ref: string): { col: number; row: number } | null {
  const m = /^\$?([A-Za-z]{1,3})\$?(\d+)$/.exec(ref.trim());
  return m ? { col: colIndex(m[1]), row: Number(m[2]) } : null;
}

export function parseRange(ref: string): { c0: number; r0: number; c1: number; r1: number } | null {
  const [a, b] = ref.split(":");
  const p = parseCell(a);
  const q = parseCell(b ?? a);
  if (!p || !q) return null;
  return { c0: Math.min(p.col, q.col), r0: Math.min(p.row, q.row), c1: Math.max(p.col, q.col), r1: Math.max(p.row, q.row) };
}

export function cellRef(col: number, row: number): string {
  return `${colLetter(col)}${row}`;
}

/** Visible row window for a virtualized list with fixed row height and overscan. */
export function visibleRows(scrollTop: number, viewport: number, rowHeight: number, total: number, overscan = 8) {
  const first = Math.max(1, Math.floor(scrollTop / rowHeight) + 1 - overscan);
  const last = Math.min(total, Math.ceil((scrollTop + viewport) / rowHeight) + overscan);
  return { first, last };
}

/** Which fixed-size blocks cover rows [first, last]. */
export function blocksFor(first: number, last: number, blockSize: number): number[] {
  const out: number[] = [];
  for (let b = Math.floor((first - 1) / blockSize); b <= Math.floor((last - 1) / blockSize); b++) out.push(b);
  return out;
}

export interface SelectionStats { count: number; numericCount: number; sum: number; average: number | null }

export function selectionStats(values: unknown[]): SelectionStats {
  let count = 0;
  let numericCount = 0;
  let sum = 0;
  for (const v of values) {
    if (v === null || v === undefined || v === "") continue;
    count++;
    if (typeof v === "number" && Number.isFinite(v)) {
      numericCount++;
      sum += v;
    }
  }
  return { count, numericCount, sum, average: numericCount ? sum / numericCount : null };
}

export function formatNumber(value: number, unit?: string | null): string {
  if (unit === "%") return `${(value * 100).toFixed(1)}%`;
  const abs = Math.abs(value);
  const text = abs >= 1000 ? abs.toLocaleString("en-US", { maximumFractionDigits: 0 }) : abs.toLocaleString("en-US", { maximumFractionDigits: 2 });
  const prefix = unit?.startsWith("USD") ? "$" : "";
  return `${value < 0 ? "-" : ""}${prefix}${text}`;
}

export function compactNumber(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${(value / 1e3).toFixed(abs >= 1e4 ? 0 : 1)}k`;
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

export function displayCellState(s: { formula: string | null; type: string; value: unknown }): string {
  if (s.formula) return s.formula;
  if (s.type === "blank" || s.value === null || s.value === undefined) return "(empty)";
  if (s.type === "date" || s.type === "datetime") return String(s.value).slice(0, 10);
  return String(s.value);
}

export function niceTicks(min: number, max: number, count = 5): number[] {
  if (min === max) return [min];
  const span = max - min;
  const step0 = span / count;
  const mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const norm = step0 / mag;
  const step = (norm >= 5 ? 10 : norm >= 2 ? 5 : norm >= 1 ? 2 : 1) * mag;
  const ticks: number[] = [];
  for (let t = Math.floor(min / step) * step; t <= max + step * 0.5; t += step) ticks.push(Number(t.toFixed(10)));
  return ticks;
}

/** Minimal, safe markdown: **bold**, `code`, line breaks and "- " lists. Returns segments, never HTML. */
export type Segment = { kind: "text" | "bold" | "code"; text: string };
export function inlineSegments(line: string): Segment[] {
  const out: Segment[] = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  for (let m = re.exec(line); m; m = re.exec(line)) {
    if (m.index > last) out.push({ kind: "text", text: line.slice(last, m.index) });
    const tok = m[0];
    out.push(tok.startsWith("**") ? { kind: "bold", text: tok.slice(2, -2) } : { kind: "code", text: tok.slice(1, -1) });
    last = m.index + tok.length;
  }
  if (last < line.length) out.push({ kind: "text", text: line.slice(last) });
  return out;
}

export function uid(): string {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

/** Approximate Excel number-format display for preview values (percent, currency, grouping, decimals). */
export function formatWithNumberFormat(value: unknown, fmt: string | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return value === null || value === undefined ? "" : String(value);
  const f = (fmt ?? "General").split(";")[0];
  const decimals = /0\.(0+)/.exec(f)?.[1].length ?? 0;
  if (f.includes("%")) return `${(value * 100).toFixed(decimals)}%`;
  if (!/[0#]/.test(f)) return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(10)));
  const currency = ["$", "€", "£"].find((c) => f.includes(c)) ?? "";
  const body = Math.abs(value).toLocaleString("en-US", {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals, useGrouping: f.includes(","),
  });
  return `${value < 0 ? "-" : ""}${currency}${body}`;
}
