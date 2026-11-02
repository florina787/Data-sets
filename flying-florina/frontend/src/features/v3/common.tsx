import type { ReactNode } from "react";
import { scale } from "@/features/global/GlobeMap";

export const REGIONS = ["Europe", "North America", "Middle East", "Asia-Pacific", "Latin America", "Africa"];
export const HORIZON_OPTIONS = [7, 14, 30, 60, 90];
export const pct = (v?: number | null, d = 0) => (v == null ? "—" : `${(v * 100).toFixed(d)}%`);
export const num = (v?: number | null, d = 2) => (v == null ? "—" : Number(v).toFixed(d));
export const usd = (v?: number | null) => (v == null ? "—" : v >= 1e6 ? `$${(v / 1e6).toFixed(2)}M` : `$${Math.round(v).toLocaleString()}`);

/** Semicircle gauge; `bad` = true when higher values are worse. */
export function Gauge({ value, label, sub, bad = false, max = 1 }: { value: number | null | undefined; label: string; sub?: string; bad?: boolean; max?: number }) {
  const v = value == null ? 0 : Math.max(0, Math.min(1, value / max));
  const a = Math.PI * (1 - v);
  const x = 50 + 40 * Math.cos(a), y = 50 - 40 * Math.sin(a);
  const col = value == null ? "#334155" : scale(bad ? v : 1 - v);
  return (
    <div className="flex flex-col items-center rounded-xl border border-token bg-white/[0.02] p-2" title={sub}>
      <svg viewBox="0 0 100 58" className="w-full max-w-[150px]" role="img" aria-label={`${label}: ${value == null ? "no data" : value}`}>
        <path d="M10 50 A40 40 0 0 1 90 50" fill="none" stroke="rgba(148,163,184,0.15)" strokeWidth="8" strokeLinecap="round" />
        {value != null && <path d={`M10 50 A40 40 0 0 1 ${x.toFixed(2)} ${y.toFixed(2)}`} fill="none" stroke={col} strokeWidth="8" strokeLinecap="round" />}
        <text x="50" y="47" textAnchor="middle" fontSize="15" fontWeight="600" fill="currentColor">{value == null ? "—" : max === 1 ? pct(value) : num(value, 1)}</text>
      </svg>
      <p className="mt-0.5 text-center text-[11px] leading-tight">{label}</p>
      {sub && <p className="text-center text-[10px] text-faint">{sub}</p>}
    </div>
  );
}

export function Select({ label, value, onChange, options, allLabel }: { label: string; value: string; onChange: (v: string) => void; options: (string | { value: string; label: string })[]; allLabel?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="label">{label}</span>
      <select className="input !py-1.5 text-sm" value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
        {allLabel !== undefined && <option value="">{allLabel}</option>}
        {options.map((o) => (typeof o === "string" ? <option key={o} value={o}>{o}</option> : <option key={o.value} value={o.value}>{o.label}</option>))}
      </select>
    </label>
  );
}

export function Banner({ children, tone = "gold" }: { children: ReactNode; tone?: "gold" | "amber" | "red" }) {
  const c = tone === "red" ? "border-neg/40 bg-neg/10" : tone === "amber" ? "border-warn/40 bg-warn/10" : "border-cyan/30 bg-cyan/5";
  return <div className={`rounded-xl border px-3 py-2 text-xs ${c}`}>{children}</div>;
}

export function Metric({ k, v, hint }: { k: string; v: ReactNode; hint?: string }) {
  return (
    <div className="rounded-lg border border-token bg-white/[0.02] px-2.5 py-1.5" title={hint}>
      <p className="text-[10px] uppercase tracking-wider text-faint">{k}</p>
      <p className="num text-sm">{v}</p>
    </div>
  );
}
