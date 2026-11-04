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

function Sparkline({ values, tone }: { values: number[]; tone: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values), max = Math.max(...values);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${28 - ((v - min) / (max - min || 1)) * 26}`).join(" ");
  return (
    <svg viewBox="0 0 100 30" preserveAspectRatio="none" className="h-7 w-full" aria-hidden>
      <polyline points={pts} fill="none" stroke={tone} strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const TONE = { good: "text-pos", warn: "text-warn", crit: "text-crit", neutral: "text-muted" } as const;
const STROKE = { good: "#10B981", warn: "#F59E0B", crit: "#EF4444", neutral: "#94a3b8" } as const;

export function FinancialKPICard({ k, index = 0, inline = false }: { k: KPI; index?: number; inline?: boolean }) {
  const v = useCountUp(k.value);
  return (
    <div className="flo-rise rounded-xl border border-line bg-card p-3.5" style={{ animationDelay: `${index * 50}ms` }} data-kpi={inline ? undefined : k.id}>
      <div className="flex items-start justify-between gap-2">
        <div className="text-xs text-muted">{k.label}</div>
        {k.provenance !== "platform_synthetic" && <Badge tone={k.provenance === "illustrative_assumption" ? "warn" : "blue"}>{PROVENANCE_LABEL[k.provenance]}</Badge>}
      </div>
      <div className="mt-1 text-2xl font-semibold tracking-tight tabular-nums">
        <span aria-hidden>{formatValue(v, k.unit)}</span><span className="sr-only">{formatValue(k.value, k.unit)}</span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs">
        {k.delta != null && <span className={cn("tabular-nums font-medium", TONE[k.status])}>{formatDelta(k.delta, k.delta_unit)}</span>}
        <span className="truncate text-muted">{k.delta_label}</span>
      </div>
      {k.trend.length > 1 && <Sparkline values={k.trend} tone={STROKE[k.status]} />}
      {k.note && <div className="mt-1 truncate text-[11px] text-muted" title={k.note}>{k.note}</div>}
    </div>
  );
}
