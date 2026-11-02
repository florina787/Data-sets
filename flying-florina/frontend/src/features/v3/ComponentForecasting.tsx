import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { LineChart as LineIcon } from "lucide-react";
import { Chart } from "@/components/Chart";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, PageHeader, Skeleton, Tabs } from "@/components/ui";
import { get } from "@/lib/api";
import { Banner, Gauge, HORIZON_OPTIONS, Metric, num, pct, REGIONS, Select, usd } from "./common";

type Row = { category_id: string; category: string; family: string; p10: number; p50: number; p90: number; labour_hours_p50: number; cost_p10_usd: number; cost_p50_usd: number;
  cost_p90_usd: number; stockout_sites: number; max_stockout_prob: number; mean_risk_30d: number | null; units_high_risk: number; repair_tat_p50_days: number | null };
type Comp = { horizon_days: number; rows: Row[]; method: string; freshness: { data_as_of: string; model_version: string; models_built_at: string } };
type Series = { category: string; history: { week_start: string; removals: number }[]; forecast: { horizon_days: number; p10: number; p50: number; p90: number }[];
  inventory: { horizon_days: number; p10: number; p50: number; p90: number; stockout_prob: number }[] };
type Unit = { id: string; category: string; category_id: string; facility: string; last_health: number | null; rul_combined?: number | null; risk_30d?: number; status: string };
type RegMetric = { mae: number; rmse: number; bias: number; n: number; coverage_80?: number; mean_interval_width?: number };
type ClsMetric = { precision: number; recall: number; f1: number; tp: number; fp: number; fn: number; positives: number; n: number };
type Evaluation = {
  metrics: {
    demand: { method: string; split: string; by_horizon: Record<string, RegMetric & { baseline_moving_average: RegMetric; baseline_seasonal_naive: RegMetric; mae_improvement_vs_moving_average: number }> };
    rul: { method: string; split: string; caveat: string; survival: RegMetric; health_trend: RegMetric; combined: RegMetric; units_scored: number };
    failure_risk_30d: { method: string; split: string; "model_at_0.5": ClsMetric; "baseline_health_below_0.35": ClsMetric; calibration: { ece: number; brier: number; bins: { bin: string; predicted: number; observed: number; n: number }[] } };
    anomaly: { method: string; ground_truth: string; split: string; isolation_forest: ClsMetric; baseline_zscore_gt3: ClsMetric };
    lead_time: RegMetric & { method: string; split: string; baseline_supplier_median: RegMetric; late_delivery: ClsMetric & { ece: number; brier: number } };
    repair_turnaround: RegMetric & { method: string; split: string };
  };
  backtest: { week_start: string; actual_total: number; p10_total: number; p50_total: number; p90_total: number; mae: number; coverage_80: number }[];
  weibull: Record<string, { k: number; eta_weeks: number; n: number; failures: number }>;
  risk_feature_importance: Record<string, number>;
  freshness: { model_version: string; build_ms: number; models_built_at: string };
};

export function ComponentForecasting() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") ?? "forecast");
  const [horizon, setHorizon] = useState(Number(params.get("horizon") ?? 90));
  const [region, setRegion] = useState(params.get("region") ?? "");
  const [cat, setCat] = useState(params.get("category") ?? "");
  const comp = useQuery({ queryKey: ["fc-comp", horizon, region], queryFn: () => get<Comp>(`/api/forecast/components?horizon=${horizon}${region ? `&region=${encodeURIComponent(region)}` : ""}`) });
  const rows = comp.data?.data.rows ?? [];
  const selected = cat || rows[0]?.category_id || "hydraulic_pump";
  const series = useQuery({ queryKey: ["fc-series", selected, region], queryFn: () => get<Series>(`/api/forecast/series?category=${selected}${region ? `&region=${encodeURIComponent(region)}` : ""}`) });
  const heat = useQuery({ queryKey: ["fc-heat", horizon], queryFn: () => get<{ x: string[]; y: string[]; cells: number[][]; unit: string }>(`/api/forecast/heatmap?horizon=${horizon}`) });
  const units = useQuery({ queryKey: ["twin-units-all"], queryFn: () => get<Unit[]>("/api/twin/units") });
  const ev = useQuery({ queryKey: ["fc-eval"], queryFn: () => get<Evaluation>("/api/forecast/evaluation"), enabled: tab === "accuracy" });
  const catOptions = useMemo(() => rows.map((r) => ({ value: r.category_id, label: r.category })), [rows]);
  if (comp.error) return <ErrorBox error={comp.error} onRetry={() => comp.refetch()} />;
  const s = series.data?.data;
  return (
    <div className="space-y-4">
      <PageHeader title="Component Forecasting Engine" icon={<LineIcon className="h-5 w-5" />}
        subtitle="Demand, inventory depletion, remaining useful life and failure risk from gradient boosting, survival analysis, random forests and seeded simulation. Every model is scored on held-out weeks against a baseline." />
      <Banner>SYNTHETIC demonstration dataset · data as of {comp.data?.data.freshness.data_as_of ?? "…"} · {comp.data?.data.freshness.model_version} · intervals are 80% prediction intervals · Qwen never produces these numbers.</Banner>
      <div className="flex flex-wrap items-end gap-3">
        <Select label="Horizon" value={String(horizon)} onChange={(v) => setHorizon(Number(v))} options={HORIZON_OPTIONS.map((h) => ({ value: String(h), label: `+${h} days` }))} />
        <Select label="Region" value={region} onChange={setRegion} options={REGIONS} allLabel="All regions" />
        <Select label="Category (detail charts)" value={selected} onChange={setCat} options={catOptions} />
      </div>
      <Tabs label="Forecasting views" active={tab} onChange={setTab} tabs={[{ id: "forecast", label: "Demand & inventory" }, { id: "health", label: "Health, RUL & risk" }, { id: "accuracy", label: "Historical accuracy" }]} />
      {tab === "forecast" && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title={`Predicted removals by category (+${horizon} days)`} subtitle={comp.data?.data.method}>
            {comp.isLoading ? <Skeleton className="h-72" /> : (
              <Chart title="demand by category" height={320} spec={{ kind: "bar", x: rows.slice(0, 12).map((r) => r.category), series: [
                { name: "P10", data: rows.slice(0, 12).map((r) => r.p10) }, { name: "P50", data: rows.slice(0, 12).map((r) => r.p50) }, { name: "P90", data: rows.slice(0, 12).map((r) => r.p90) }] }} />
            )}
          </Card>
          <Card title={`${s?.category ?? "…"}: history and forecast fan`} subtitle="Weekly removals (26 weeks) then cumulative forecast P10/P50/P90">
            {s ? <Chart title="series" height={320} spec={{ kind: "line", x: [...s.history.slice(-26).map((h) => h.week_start.slice(5)), ...s.forecast.map((f) => `+${f.horizon_days}d`)], series: [
              { name: "weekly removals", data: [...s.history.slice(-26).map((h) => h.removals), ...s.forecast.map(() => null)] as number[] },
              { name: "P10", data: [...s.history.slice(-26).map(() => null), ...s.forecast.map((f) => f.p10)] as number[] },
              { name: "P50", data: [...s.history.slice(-26).map(() => null), ...s.forecast.map((f) => f.p50)] as number[] },
              { name: "P90", data: [...s.history.slice(-26).map(() => null), ...s.forecast.map((f) => f.p90)] as number[] }] }} /> : <Skeleton className="h-72" />}
          </Card>
          <Card title={`${s?.category ?? "…"}: inventory depletion curve`} subtitle="Projected on-hand units with a weekly reorder policy (negative = backorders); stockout probability on the right">
            {s ? <Chart title="inventory" height={280} spec={{ kind: "line", x: s.inventory.map((i) => (i.horizon_days ? `+${i.horizon_days}d` : "today")), series: [
              { name: "on hand P10", data: s.inventory.map((i) => i.p10) }, { name: "on hand P50", data: s.inventory.map((i) => i.p50) }, { name: "on hand P90", data: s.inventory.map((i) => i.p90) },
              { name: "stockout probability", data: s.inventory.map((i) => i.stockout_prob) }] }} /> : <Skeleton className="h-64" />}
          </Card>
          <Card title="Maintenance demand heatmap" subtitle={heat.data?.data.unit}>
            {heat.data ? <Chart title="heatmap" height={420} spec={{ kind: "heatmap", x: heat.data.data.x, y: heat.data.data.y, cells: heat.data.data.cells, series: [] }} /> : <Skeleton className="h-80" />}
          </Card>
          <div className="xl:col-span-2">
            <Card title="Forecast detail by category">
              <DataTable rows={rows as unknown as Record<string, unknown>[]} columns={[{ key: "category", label: "Category" }, { key: "p10", label: "P10" }, { key: "p50", label: "P50" }, { key: "p90", label: "P90" },
                { key: "labour_hours_p50", label: "Labour h P50" }, { key: "cost_p50_usd", label: "Cost P50 USD" }, { key: "stockout_sites", label: "Sites ≥20% stockout" },
                { key: "mean_risk_30d", label: "Mean 30-day risk" }, { key: "repair_tat_p50_days", label: "Repair TAT P50 (d)" }]} />
            </Card>
          </div>
        </div>
      )}
      {tab === "health" && <HealthTab units={units.data?.data ?? []} rows={rows} />}
      {tab === "accuracy" && (ev.data ? <AccuracyTab e={ev.data.data} /> : ev.error ? <ErrorBox error={ev.error} /> : <Skeleton className="h-96" />)}
    </div>
  );
}

function HealthTab({ units, rows }: { units: Unit[]; rows: Row[] }) {
  const byCat = useMemo(() => {
    const m: Record<string, { h: number[]; r: number[] }> = {};
    units.forEach((u) => {
      const x = (m[u.category] ??= { h: [], r: [] });
      if (u.last_health != null) x.h.push(u.last_health);
      if (u.risk_30d != null) x.r.push(u.risk_30d);
    });
    return Object.entries(m).map(([k, v]) => ({ cat: k, health: v.h.reduce((a, b) => a + b, 0) / Math.max(1, v.h.length), risk: v.r.reduce((a, b) => a + b, 0) / Math.max(1, v.r.length) }))
      .sort((a, b) => a.health - b.health);
  }, [units]);
  const rul = units.map((u) => u.rul_combined).filter((v): v is number => v != null);
  const bins = [0, 4, 8, 13, 26, 52, 104, 1e9];
  const hist = bins.slice(0, -1).map((b, i) => rul.filter((v) => v >= b && v < bins[i + 1]).length);
  return (
    <div className="space-y-4">
      <Card title="Component health gauges" subtitle="Mean latest health index of installed tracked units per category (1 = new, 0.2 = removal threshold)">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-5">
          {byCat.slice(0, 10).map((c) => <Gauge key={c.cat} value={c.health} label={c.cat} sub={`mean 30-day risk ${pct(c.risk, 1)}`} />)}
        </div>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Remaining useful life distribution" subtitle={`${rul.length} installed units · weeks`}>
          <Chart title="rul" height={280} spec={{ kind: "bar", x: ["<4", "4–8", "8–13", "13–26", "26–52", "52–104", "≥104"], series: [{ name: "units", data: hist }] }} />
        </Card>
        <Card title="Failure-risk comparison" subtitle="Mean 30-day removal probability (RandomForest) vs units at ≥50% risk">
          <Chart title="risk" height={280} spec={{ kind: "bar", x: rows.slice(0, 12).map((r) => r.category), series: [{ name: "mean 30-day risk", data: rows.slice(0, 12).map((r) => r.mean_risk_30d ?? 0) },
            { name: "units ≥50% risk", data: rows.slice(0, 12).map((r) => r.units_high_risk) }] }} />
        </Card>
      </div>
    </div>
  );
}

function AccuracyTab({ e }: { e: Evaluation }) {
  const d = e.metrics.demand.by_horizon;
  const r = e.metrics.failure_risk_30d;
  const a = e.metrics.anomaly;
  const lt = e.metrics.lead_time;
  return (
    <div className="space-y-4">
      <Banner tone="amber">Held-out evaluation on the synthetic dataset (temporal split; last 26 weeks never used for fitting). Where a simpler baseline wins, it is shown as winning.</Banner>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="7-day backtest: actual vs forecast (all MRO hubs)" subtitle="Rolling origin over the 26 held-out weeks">
          <Chart title="backtest" height={300} spec={{ kind: "line", x: e.backtest.map((b) => b.week_start.slice(5)), series: [
            { name: "actual", data: e.backtest.map((b) => b.actual_total) }, { name: "P50", data: e.backtest.map((b) => b.p50_total) },
            { name: "P10", data: e.backtest.map((b) => b.p10_total) }, { name: "P90", data: e.backtest.map((b) => b.p90_total) }] }} />
        </Card>
        <Card title="Demand MAE by horizon: model vs baselines" subtitle={e.metrics.demand.method}>
          <Chart title="mae" height={300} spec={{ kind: "bar", x: Object.keys(d), series: [{ name: "model", data: Object.values(d).map((v) => v.mae) },
            { name: "moving average", data: Object.values(d).map((v) => v.baseline_moving_average.mae) }, { name: "seasonal naive", data: Object.values(d).map((v) => v.baseline_seasonal_naive.mae) }] }} />
        </Card>
        <Card title="Prediction interval coverage (target 80%)" subtitle="Split-conformal intervals; long horizons under-cover">
          <Chart title="coverage" height={260} spec={{ kind: "bar", x: Object.keys(d), series: [{ name: "coverage", data: Object.values(d).map((v) => v.coverage_80 ?? 0) }], markLine: { y: 0.8, label: "80% target" } }} />
          <p className="mt-1 text-xs muted">Bias (P50 − actual): {Object.entries(d).map(([k, v]) => `${k} ${num(v.bias)}`).join(" · ")}</p>
        </Card>
        <Card title="Failure-risk calibration (reliability)" subtitle={`ECE ${r.calibration.ece} · Brier ${r.calibration.brier}`}>
          <Chart title="calibration" height={260} spec={{ kind: "line", x: r.calibration.bins.map((b) => b.bin), series: [{ name: "predicted", data: r.calibration.bins.map((b) => b.predicted) },
            { name: "observed", data: r.calibration.bins.map((b) => b.observed) }] }} />
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Failure within 30 days">
          <div className="grid grid-cols-3 gap-2">
            <Metric k="Precision" v={num(r["model_at_0.5"].precision)} /><Metric k="Recall" v={num(r["model_at_0.5"].recall)} /><Metric k="F1" v={num(r["model_at_0.5"].f1)} />
          </div>
          <p className="mt-2 text-xs muted">Baseline (health &lt; 0.35): F1 {num(r["baseline_health_below_0.35"].f1)} · {r["model_at_0.5"].positives} positives in {r["model_at_0.5"].n} unit-weeks</p>
        </Card>
        <Card title="Anomaly detection">
          <div className="grid grid-cols-2 gap-2">
            <Metric k="IsolationForest F1" v={num(a.isolation_forest.f1)} /><Metric k="z-score rule F1" v={num(a.baseline_zscore_gt3.f1)} />
          </div>
          <p className="mt-2 text-xs muted">{a.baseline_zscore_gt3.f1 > a.isolation_forest.f1 ? "The simple z-score rule outperforms the IsolationForest on this data." : "The IsolationForest outperforms the z-score rule."} Labels: {a.ground_truth}.</p>
        </Card>
        <Card title="Supplier lead time & repair TAT">
          <div className="grid grid-cols-2 gap-2">
            <Metric k="Lead-time MAE (d)" v={num(lt.mae, 1)} /><Metric k="Supplier-median MAE" v={num(lt.baseline_supplier_median.mae, 1)} />
            <Metric k="Lead-time 80% coverage" v={pct(lt.coverage_80)} /><Metric k="Repair TAT coverage" v={pct(e.metrics.repair_turnaround.coverage_80)} />
          </div>
        </Card>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Remaining useful life (weeks)" subtitle={e.metrics.rul.caveat}>
          <div className="grid grid-cols-3 gap-2">
            <Metric k="Survival MAE" v={num(e.metrics.rul.survival.mae, 1)} /><Metric k="Health-trend MAE" v={num(e.metrics.rul.health_trend.mae, 1)} /><Metric k="Units scored" v={e.metrics.rul.units_scored} />
          </div>
        </Card>
        <Card title="Weibull survival fits (per category)">
          <DataTable rows={Object.entries(e.weibull).map(([k, v]) => ({ category: k, ...v }))} columns={[{ key: "category", label: "Category" }, { key: "k", label: "shape k" },
            { key: "eta_weeks", label: "scale η (weeks)" }, { key: "failures", label: "failures" }, { key: "n", label: "units" }]} />
        </Card>
      </div>
      <p className="text-xs text-faint">Models built {e.freshness.models_built_at} in {Math.round(e.freshness.build_ms)} ms · {e.freshness.model_version} · <Badge tone="gold">synthetic</Badge> · costs shown elsewhere use {usd(95)}/labour hour (assumption)</p>
    </div>
  );
}
