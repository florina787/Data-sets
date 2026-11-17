import { SUGAR_IDEAL_PCT, SUGAR_LIMIT_PCT, sugarLevel, sugarPct } from "./engine";
import type { Nutrients } from "./foods";

/** Added sugar as % of calories, against WHO 5% / 10% marks. */
export function SugarGauge({ n, label = "Added sugar" }: { n: Partial<Nutrients>; label?: string }) {
  const pct = sugarPct(n);
  const lvl = sugarLevel(pct);
  const color = lvl === "high" ? "var(--f-danger)" : lvl === "moderate" ? "var(--f-warn)" : "var(--f-good)";
  const width = pct === null ? 0 : Math.min(pct / 20, 1) * 100;
  const text = pct === null ? "No data" : `${pct}% of calories`;
  return (
    <div aria-label={`${label}: ${text}. WHO advises under 10%, ideally under 5%.`}>
      <div className="flex items-baseline justify-between"><span className="text-sm">{label}</span><span className="font-display text-2xl" style={{ color }}>{pct === null ? "–" : `${pct}%`}</span></div>
      <div className="relative mt-2 h-3 rounded-full bg-surface-2">
        <div className="h-full rounded-full" style={{ width: `${width}%`, background: color }} />
        <span className="absolute top-[-4px] h-5 w-0.5 bg-muted" style={{ left: `${(SUGAR_IDEAL_PCT / 20) * 100}%` }} title="5%" />
        <span className="absolute top-[-4px] h-5 w-0.5 bg-ink" style={{ left: `${(SUGAR_LIMIT_PCT / 20) * 100}%` }} title="10%" />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted"><span>0%</span><span style={{ marginLeft: "15%" }}>5% ideal</span><span>10% limit</span><span>20%+</span></div>
      <p className="mt-1 text-xs text-muted">{lvl === "unknown" ? (n.kcal ? "Sugar data missing for this item." : "Log a meal to see your sugar percentage.") : lvl === "low" ? "Within the WHO ideal of under 5%." : lvl === "moderate" ? "Under the WHO limit of 10%, above the 5% ideal." : "Above the WHO limit of 10% of calories."}</p>
    </div>
  );
}
