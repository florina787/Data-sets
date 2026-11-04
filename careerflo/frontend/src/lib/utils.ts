import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...v: ClassValue[]) => twMerge(clsx(v));

export function money(n?: number | null, cur?: string | null) {
  if (n == null) return "—";
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: cur || "CAD", maximumFractionDigits: 0 }).format(n);
}

export function salaryRange(j: { salary_min?: number | null; salary_max?: number | null; salary_currency?: string | null }) {
  if (!j.salary_min && !j.salary_max) return "Salary not published";
  const c = j.salary_currency || "CAD";
  const k = (x?: number | null) => (x ? `${Math.round(x / 1000)}k` : "");
  return `${c} ${k(j.salary_min)}${j.salary_max ? `–${k(j.salary_max)}` : ""}`;
}

export function ago(iso?: string | null) {
  if (!iso) return "";
  const h = Math.floor((Date.now() - new Date(iso).getTime()) / 36e5);
  if (h < 24) return "Posted today";
  const d = Math.floor(h / 24);
  return d === 1 ? "Posted 1 day ago" : `Posted ${d} days ago`;
}

export const idem = () => (crypto?.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2));
