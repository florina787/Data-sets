import { useEffect, useRef, useState } from "react";
import { Badge, cn } from "@/components/ui";
import { formatDelta, formatValue, PROVENANCE_LABEL, prefersReducedMotion } from "../format";
import type { KPI } from "../types";

function useCountUp(target: number | null, ms = 700) {
  const [v, setV] = useState<number | null>(prefersReducedMotion() ? target : target == null ? null : 0);
  const raf = useRef(0);
  useEffect(() => {
    if (target == null || prefersReducedMotion()) { setV(target); return; }
    const t0 = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - t0) / ms);
      setV(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target, ms]);
  return v;
}

function Sparkline({ values, tone, id }: { values: number[]; tone: string; id: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const pts = values.map((v, i) => [(i / (values.length - 1)) * 100, 26 - ((v - min) / (max - min || 1)) * 22] as const);
  // smooth curve through the points (Catmull-Rom → cubic Bézier), then an area that fades out below it
  const d = pts.map((p, i) => {
    if (i === 0) return `M${p[0]},${p[1]}`;
    const p0 = pts[i - 2] ?? pts[i - 1], p1 = pts[i - 1], p3 = pts[i + 1] ?? p;
    return `C${p1[0] + (p[0] - p0[0]) / 6},${p1[1] + (p[1] - p0[1]) / 6} ${p[0] - (p3[0] - p1[0]) / 6},${p[1] - (p3[1] - p1[1]) / 6} ${p[0]},${p[1]}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="mt-1 h-9 w-full" aria-hidden>
      <defs><linearGradient id={`spark-${id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor={tone} stopOpacity="0.32" /><stop offset="1" stopColor={tone} stopOpacity="0" /></linearGradient></defs>
      <path d={`${d} L100,30 L0,30 Z`} fill={`url(#spark-${id})`} />
      <path d={d} fill="none" stroke={tone} strokeWidth="1.8" vectorEffect="non-scaling-stroke" strokeLinecap="round" />
    </svg>
  );
}

const TONE = { good: "text-pos", warn: "text-warn", crit: "text-crit", neutral: "text-muted" } as const;
const PILL = { good: "bg-pos/15", warn: "bg-warn/15", crit: "bg-crit/15", neutral: "bg-line/50" } as const;
const STROKE = { good: "#C8E06B", warn: "#E2C766", crit: "#EF6B6B", neutral: "#94a3b8" } as const;

export function FinancialKPICard({ k, index = 0, inline = false }: { k: KPI; index?: number; inline?: boolean }) {
  const v = useCountUp(k.value);
  return (
    <div className="flo-rise rounded-2xl border border-line/70 bg-gradient-to-b from-card to-card/70 p-4" style={{ animationDelay: `${index * 50}ms` }} data-kpi={inline ? undefined : k.id}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs text-muted">{k.label}</div>
        {k.provenance !== "platform_synthetic" && <Badge tone={k.provenance === "illustrative_assumption" ? "warn" : "blue"}>{PROVENANCE_LABEL[k.provenance]}</Badge>}
      </div>
      <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
        <span aria-hidden>{formatValue(v, k.unit)}</span><span className="sr-only">{formatValue(k.value, k.unit)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {k.delta != null && <span className={cn("rounded-full px-2 py-0.5 tabular-nums font-medium", TONE[k.status], PILL[k.status])}>{formatDelta(k.delta, k.delta_unit)}</span>}
        <span className="truncate text-muted">{k.delta_label}</span>
      </div>
      {k.trend.length > 1 && <Sparkline values={k.trend} tone={STROKE[k.status]} id={`${k.id}${inline ? "-i" : ""}`} />}
      {k.note && <div className="mt-1 truncate text-[11px] text-muted" title={k.note}>{k.note}</div>}
    </div>
  );
}
