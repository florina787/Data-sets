// FLOW WEALTH metric components in FLO's gold-to-lime language: dot-matrix and bar sparklines, gradient progress rows,
// a glossy lime bar chart, a glowing insight card and an "explore next" prompt that hands the question to FLO.
// Every value shown comes from an API response; nothing here is decorative data.
import { Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { EChart } from "@/components/EChart";
import { Badge, Card, cn } from "@/components/ui";
import { HERO_STROKE, hexA, linear } from "@/flo/chartOptions";
import { useApp } from "@/lib/app";
import { tokens } from "@/lib/chartTheme";

export const LIME = "#C8E06B";
export const LIME_DEEP = "#6E8F1F";

/** Data-status badge: every market view says whether it shows historical data or an unvalidated research result. */
export function DataStatus({ kind, asOf }: { kind: "historical" | "research"; asOf?: string }) {
  return kind === "historical"
    ? <Badge tone="gold" title="Kaggle historical dataset; not a current market feed">Historical data{asOf ? ` · ends ${asOf}` : ""} · not live</Badge>
    : <Badge tone="warn" title="Model outputs failed validation; research only">Research result · not validated</Badge>;
}

/** Column of dots per value (dot-matrix sparkline). */
export function DotBars({ values, rows = 6, label }: { values: number[]; rows?: number; label: string }) {
  const max = Math.max(...values.map(Math.abs), 1e-12);
  const w = 7, gap = 3;
  return (
    <svg width={values.length * (w + gap)} height={rows * (w + gap)} role="img" aria-label={label} className="shrink-0">
      {values.map((v, i) => {
        const on = Math.max(1, Math.round((Math.abs(v) / max) * rows));
        return Array.from({ length: rows }, (_, r) => (
          <circle key={`${i}-${r}`} cx={i * (w + gap) + w / 2} cy={(rows - 1 - r) * (w + gap) + w / 2} r={w / 2 - 0.5}
            fill={r < on ? (v < 0 ? "#EF4444" : LIME) : "rgba(148,163,184,0.14)"} />
        ));
      })}
    </svg>
  );
}

/** Thin vertical bars (retention-style sparkline). */
export function BarSpark({ values, color = "#E8A6C8", label, height = 64 }: { values: number[]; color?: string; label: string; height?: number }) {
  const lo = Math.min(...values), hi = Math.max(...values), span = hi - lo || 1;
  return (
    <div role="img" aria-label={label} className="flex items-end gap-[2px]" style={{ height }}>
      {values.map((v, i) => <div key={i} className="w-[3px] rounded-t" style={{ height: `${12 + ((v - lo) / span) * 88}%`, background: color, opacity: 0.85 }} />)}
    </div>
  );
}

export function MetricCard({ title, value, sub, pill, children, className }: {
  title: string; value: ReactNode; sub?: ReactNode; pill?: ReactNode; children?: ReactNode; className?: string;
}) {
  return (
    <Card className={cn("flex flex-col gap-2 rounded-2xl p-4", className)}>
      <div className="flex items-center justify-between gap-2"><h3 className="text-sm font-semibold">{title}</h3>{pill}</div>
      <div className="flex items-end justify-between gap-3">
        <div>
          <div className="font-mono text-3xl font-semibold tracking-tight">{value}</div>
          {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
        </div>
        {children}
      </div>
    </Card>
  );
}

export function ProgressRows({ rows, label }: { rows: { label: string; value: string; share: number; tone?: "lime" | "blue" | "pink" }[]; label: string }) {
  const col = { lime: `linear-gradient(90deg, ${LIME_DEEP}, ${LIME})`, blue: "linear-gradient(90deg,#2f5fb3,#7fb2ff)", pink: "linear-gradient(90deg,#9c3f73,#f0a4cf)" };
  return (
    <ul className="space-y-3" aria-label={label}>
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1 flex justify-between text-xs"><span>{r.label}</span><span className="font-mono">{r.value}</span></div>
          <div className="h-2.5 rounded-full bg-line/50" role="progressbar" aria-label={r.label} aria-valuenow={Math.round(r.share * 100)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-2.5 rounded-full" style={{ width: `${Math.max(2, Math.min(100, r.share * 100))}%`, background: col[r.tone ?? "lime"] }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Glowing insight card: one large figure and a sentence, e.g. the model verdict. */
export function InsightCard({ value, title, detail, tone = "lime" }: { value: string; title: string; detail?: string; tone?: "lime" | "warn" }) {
  const glow = tone === "lime" ? "rgba(200,224,107,0.35)" : "rgba(245,158,11,0.30)";
  return (
    <Card className="relative overflow-hidden rounded-2xl p-5" style={{ backgroundImage: `radial-gradient(120% 90% at 85% 15%, ${glow}, transparent 60%)` }}>
      <Badge tone="neutral" className="mb-3"><Sparkles className="h-3 w-3" />Insight</Badge>
      <div className={cn("font-mono text-5xl font-semibold tracking-tight", tone === "lime" ? "text-[#C8E06B]" : "text-warn")}>{value}</div>
      <div className="mt-3 text-sm font-medium">{title}</div>
      {detail && <p className="mt-1 text-xs text-muted">{detail}</p>}
    </Card>
  );
}

/** Glossy lime bars; one bar may be highlighted with a hatched fill. Negative values are drawn below zero in red. */
export function GlossyBars({ categories, values, highlight, unitFmt, height = 260, ariaLabel }: {
  categories: string[]; values: number[]; highlight?: number; unitFmt: (v: number) => string; height?: number; ariaLabel: string;
}) {
  const tk = tokens();
  const option = {
    grid: { left: 48, right: 12, top: 28, bottom: 28, containLabel: true },
    tooltip: { trigger: "axis", backgroundColor: tk.surface, borderColor: tk.grid, textStyle: { color: tk.ink }, valueFormatter: unitFmt },
    xAxis: { type: "category", data: categories, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: tk.muted, fontSize: 11 } },
    yAxis: { type: "value", axisLabel: { color: tk.muted, formatter: unitFmt }, splitLine: { lineStyle: { color: "rgba(148,163,184,0.08)" } } },
    series: [{
      type: "bar", barWidth: "58%", data: values.map((v, i) => ({
        value: v,
        itemStyle: {
          borderRadius: v >= 0 ? [8, 8, 2, 2] : [2, 2, 8, 8],
          color: v < 0 ? linear("v", [[0, "#7f1d1d"], [1, "#EF4444"]]) : linear("v", [[0, "#E6F5A8"], [0.45, LIME], [1, hexA(LIME_DEEP, 0.55)]]),
          shadowColor: v < 0 ? "rgba(239,68,68,0.3)" : hexA(LIME, 0.35), shadowBlur: 14,
          decal: i === highlight ? { symbol: "rect", dashArrayX: [1, 0], dashArrayY: [3, 5], rotation: -Math.PI / 4, color: "rgba(0,0,0,0.25)" } : undefined,
        },
      })),
      label: { show: true, position: "top", color: tk.muted, fontSize: 10, formatter: (p: any) => unitFmt(p.value) },
    }],
  };
  return <EChart option={option as any} height={height} ariaLabel={ariaLabel} />;
}

/** Gold-to-lime hero line for one series plus muted comparisons. */
export function heroLineOption(dates: string[], series: { name: string; values: (number | null)[]; hero?: boolean; dashed?: boolean }[], fmt: (v: number) => string) {
  const tk = tokens();
  return {
    grid: { left: 48, right: 16, top: 30, bottom: 28, containLabel: true },
    legend: { top: 0, textStyle: { color: tk.muted }, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
    tooltip: { trigger: "axis", backgroundColor: tk.surface, borderColor: tk.grid, textStyle: { color: tk.ink }, valueFormatter: fmt },
    xAxis: { type: "category", data: dates, boundaryGap: false, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: tk.muted, hideOverlap: true } },
    yAxis: { type: "value", scale: true, axisLabel: { color: tk.muted, formatter: fmt }, splitLine: { lineStyle: { color: "rgba(148,163,184,0.07)" } } },
    series: series.map((s, i) => s.hero ? {
      name: s.name, type: "line", data: s.values, smooth: 0.3, showSymbol: false,
      lineStyle: { width: 2.6, color: linear("h", [[0, HERO_STROKE[0]], [0.55, HERO_STROKE[1]], [1, HERO_STROKE[2]]]), shadowColor: hexA(HERO_STROKE[1], 0.45), shadowBlur: 12 },
      itemStyle: { color: HERO_STROKE[1] }, areaStyle: { color: linear("v", [[0, hexA(HERO_STROKE[1], 0.28)], [1, hexA(HERO_STROKE[1], 0)]]) },
    } : {
      name: s.name, type: "line", data: s.values, smooth: 0.3, showSymbol: false,
      lineStyle: { width: 1.8, type: s.dashed ? "dashed" : "solid", color: tk.series[i % tk.series.length] }, itemStyle: { color: tk.series[i % tk.series.length] },
    }),
  };
}

/** "What would you like to explore next?" — sends the question to FLO's governed conversation. */
export function ExplorePrompt({ suggestions }: { suggestions: string[] }) {
  const { ask } = useApp();
  const [q, setQ] = useState("");
  return (
    <Card className="rounded-2xl border-line/70 bg-card/80 p-3 backdrop-blur">
      <div className="mb-2 text-sm">What would you like to explore next?</div>
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) ask({ question: q.trim(), page: "markets" }); }}>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask FLO about this data…" aria-label="Ask FLO about this data"
          className="h-9 flex-1 rounded-lg border border-line bg-bg/60 px-3 text-sm outline-none focus:border-[#C8E06B]" maxLength={500} />
        <button type="submit" className="rounded-lg px-3 text-sm font-medium text-black" style={{ background: LIME }}>Ask</button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {suggestions.map((s) => <button key={s} type="button" onClick={() => ask({ question: s, page: "markets" })}
          className="rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:border-[#C8E06B] hover:text-ink">{s}</button>)}
      </div>
    </Card>
  );
}
