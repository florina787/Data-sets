import { useMutation, useQuery } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ChartCard, DataGrid } from "@/components/ChartCard";
import { Button, Card, ErrorState, Label, PageHeader, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { bn, compact, mn, pct } from "@/lib/format";

const PRESETS = ["base", "bull", "bear", "severe_stress"] as const;
const SLIDERS: { key: string; label: string; min: number; max: number; step: number; fmt: (v: number) => string }[] = [
  { key: "equity_shock", label: "Equity market change", min: -0.5, max: 0.3, step: 0.01, fmt: (v) => pct(v, 0) },
  { key: "bond_shock", label: "Bond market change", min: -0.1, max: 0.1, step: 0.005, fmt: (v) => pct(v, 1) },
  { key: "rate_shock_bps", label: "Interest-rate shock (bps)", min: -200, max: 300, step: 25, fmt: (v) => `${v} bps` },
  { key: "inflation", label: "Inflation", min: 0, max: 0.08, step: 0.005, fmt: (v) => pct(v, 1) },
  { key: "net_flows_pct", label: "Net client flows (% AUM p.a.)", min: -0.15, max: 0.1, step: 0.01, fmt: (v) => pct(v, 0) },
  { key: "stress_redemptions_pct", label: "Stress redemptions at t0", min: 0, max: 0.15, step: 0.01, fmt: (v) => pct(v, 0) },
  { key: "fee_compression_bps", label: "Fee compression (bps)", min: 0, max: 20, step: 1, fmt: (v) => `${v} bps` },
  { key: "opex_growth", label: "Operating expense growth", min: -0.05, max: 0.15, step: 0.01, fmt: (v) => pct(v, 0) },
  { key: "tech_investment", label: "Technology investment (CAD)", min: 0, max: 50_000_000, step: 1_000_000, fmt: (v) => `CAD ${compact(v)}` },
];

export default function Scenarios() {
  const presets = useQuery({ queryKey: ["presets"], queryFn: () => api("/api/scenarios/presets") });
  const compare = useQuery({ queryKey: ["compare"], queryFn: () => api("/api/scenarios/compare") });
  const sens = useQuery({ queryKey: ["sens"], queryFn: () => api("/api/scenarios/sensitivity") });
  const [preset, setPreset] = useState<string>("base");
  const [vals, setVals] = useState<Record<string, number>>({});
  const run = useMutation({ mutationFn: (body: object) => api("/api/scenarios/run", { method: "POST", json: body }) });
  useEffect(() => {
    if (presets.data) {
      setVals({ ...presets.data.defaults, ...presets.data.presets[preset] });
      run.mutate({ preset });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [presets.data, preset]);
  const overrides = () => Object.fromEntries(SLIDERS.map((s) => [s.key, vals[s.key]]));
  const tk = tokens();
  const r = run.data;
  const pathOpt = useMemo(() => r && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => bn(v) },
    xAxis: axis({ type: "category", data: r.aum_path.map((_: any, i: number) => `M${i}`) }), yAxis: axis({ type: "value", scale: true, axisLabel: { color: tk.muted, formatter: compact } }),
    series: [{ name: "Scenario AUM", type: "line", data: r.aum_path, symbolSize: 6, lineStyle: { width: 2 }, areaStyle: { opacity: 0.15 } }] }), [r, tk]);
  const cmpOpt = useMemo(() => compare.data && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => mn(v) },
    xAxis: axis({ type: "category", data: compare.data.scenarios.map((s: any) => s.scenario.replace("_", " ")) }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
    series: [{ name: "Revenue", type: "bar", data: compare.data.scenarios.map((s: any) => s.revenue), itemStyle: { borderRadius: 4 } },
      { name: "Expenses", type: "bar", data: compare.data.scenarios.map((s: any) => s.expenses), itemStyle: { borderRadius: 4 } },
      { name: "Operating income", type: "bar", data: compare.data.scenarios.map((s: any) => s.operating_income), itemStyle: { borderRadius: 4 } }] }), [compare.data, tk]);
  const tornOpt = useMemo(() => sens.data && ({ ...baseOption(), grid: { left: 10, right: 20, top: 30, bottom: 10, containLabel: true },
    tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => mn(v) },
    yAxis: axis({ type: "category", inverse: true, data: sens.data.tornado.map((t: any) => `${t.driver} ±${t.step}`) }), xAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
    series: [{ name: "Driver down", type: "bar", stack: "t", data: sens.data.tornado.map((t: any) => Number(t.operating_income_low)), itemStyle: { color: tk.series[1], borderRadius: 3 } },
      { name: "Driver up", type: "bar", stack: "t2", data: sens.data.tornado.map((t: any) => Number(t.operating_income_high)), itemStyle: { color: tk.series[0], borderRadius: 3 } }] }), [sens.data, tk]);
  const mandOpt = useMemo(() => r?.portfolio_impacts && ({ ...baseOption(), grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
    tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v) },
    yAxis: axis({ type: "category", data: Object.keys(r.portfolio_impacts.by_mandate) }), xAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
    series: [{ type: "bar", data: Object.values(r.portfolio_impacts.by_mandate).map((v: any) => ({ value: v, itemStyle: { color: v >= 0 ? tk.series[2] : tk.series[1], borderRadius: 3 } })) }] }), [r, tk]);
  return (
    <div className="space-y-4">
      <PageHeader title="Scenario Simulator & Strategy Twin" subtitle="Deterministic models; outputs are conditional on stated assumptions — no probabilities or confidence intervals are implied." />
      <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card className="space-y-3 p-4">
          <div className="flex flex-wrap gap-1">{PRESETS.map((p) => <Button key={p} size="sm" variant={preset === p ? "primary" : "secondary"} onClick={() => setPreset(p)}>{p.replace("_", " ")}</Button>)}</div>
          {SLIDERS.map((s) => (
            <div key={s.key}>
              <div className="flex justify-between"><Label>{s.label}</Label><span className="text-xs tabular-nums">{s.fmt(vals[s.key] ?? 0)}</span></div>
              <input type="range" className="w-full accent-[#D4AF37]" aria-label={s.label} min={s.min} max={s.max} step={s.step} value={vals[s.key] ?? 0}
                onChange={(e) => setVals({ ...vals, [s.key]: Number(e.target.value) })} />
            </div>
          ))}
          <Button variant="primary" className="w-full" onClick={() => run.mutate({ preset, ...overrides() })} disabled={run.isPending}><Play className="h-4 w-4" />Run scenario</Button>
        </Card>
        <div className="space-y-4">
          {run.isPending && <Spinner label="Running deterministic model" />}
          {run.error && <ErrorState error={run.error} />}
          {r && (
            <>
              <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
                <Stat label="Estimated AUM" value={bn(r.results.aum_end)} sub={`${pct(r.results.aum_change_pct)} from ${bn(r.results.aum_start)}`} tone={r.results.aum_change_pct >= 0 ? "good" : "crit"} />
                <Stat label="Estimated revenue" value={mn(r.results.revenue)} sub={`yield ${r.results.revenue_yield_bps} bps`} />
                <Stat label="Expenses" value={mn(r.results.expenses)} />
                <Stat label="Operating income" value={mn(r.results.operating_income)} tone={Number(r.results.operating_income) >= 0 ? "good" : "crit"} />
                <Stat label="Operating margin" value={pct(r.results.operating_margin)} />
              </div>
              <div className="grid gap-4 xl:grid-cols-2">
                <ChartCard id="scenario" title="AUM path over horizon" option={pathOpt} rows={r.by_asset_class} />
                <ChartCard id="scenario" title="Portfolio impact by mandate (immediate shock)" subtitle={`${r.portfolio_impacts.count} portfolios · total ${mn(r.portfolio_impacts.total_impact)}`} option={mandOpt} rows={r.portfolio_impacts.most_impacted} />
              </div>
              <ChartCard id="scenario" title="Assumption traceability"><DataGrid rows={r.assumptions.map((a: any) => ({ ...a, value: String(a.value) }))} />
                <p className="mt-2 text-xs text-muted">{r.method} Fixed: {Object.entries(r.fixed_assumptions).map(([k, v]) => `${k}=${v}`).join("; ")}</p></ChartCard>
            </>
          )}
          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard id="scenario" title="Scenario comparison (base / bull / bear / severe)" option={cmpOpt} loading={compare.isLoading} error={compare.error} rows={compare.data?.scenarios} />
            <ChartCard id="scenario" title="Sensitivity of operating income (tornado)" subtitle={sens.data?.method} option={tornOpt} loading={sens.isLoading} error={sens.error} rows={sens.data?.tornado} />
          </div>
        </div>
      </div>
    </div>
  );
}
