import { useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { DataStatus, ExplorePrompt, GlossyBars, InsightCard, MetricCard, heroLineOption } from "@/components/MarketMetrics";
import { Badge, Card, ErrorState, PageHeader, Spinner, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { num, pct } from "@/lib/format";

type H = "1" | "5" | "20";
const ch = createColumnHelper<any>();
const CSV_RES = "# RESEARCH RESULT - not validated - Kaggle kaggle-us-stocks-etfs-v3 holdout - survivorship-biased universe";

export default function ResearchLab() {
  const q = useQuery({ queryKey: ["mkt-research"], queryFn: () => api("/api/markets/research"), retry: false });
  const [h, setH] = useState<H>("5");
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const r = q.data;
  const hr = r.horizons[h];
  const models = Object.entries(hr.models).map(([name, m]: [string, any]) => ({ name, ...m }));
  const traded = models.filter((m) => m.net_sharpe != null);
  const dec = Object.values(r.horizons).flatMap((x: any) => x.decisions);
  const rejected = dec.filter((d: any) => !d.eligible).length;
  const best = hr.models[hr.best_by_ic];
  const cols = [
    ch.accessor("name", { header: "Model", cell: (c) => <span className="font-medium">{c.getValue()}{c.row.original.family === "baseline" && <Badge tone="neutral" className="ml-1">baseline</Badge>}</span> }),
    ch.accessor("ic_mean", { header: "Rank IC", cell: (c) => num(c.getValue(), 4) }), ch.accessor("ic_t", { header: "IC t (indep.)", cell: (c) => num(c.getValue(), 2) }),
    ch.accessor("directional_accuracy", { header: "Direction", cell: (c) => pct(c.getValue(), 1) }),
    ch.accessor("top_decile_precision", { header: "Top-decile precision", cell: (c) => pct(c.getValue(), 1) }),
    ch.accessor("gross_sharpe", { header: "Gross Sharpe", cell: (c) => num(c.getValue(), 2) }),
    ch.accessor("net_sharpe", { header: "Net Sharpe", cell: (c) => <span className={(c.getValue() ?? 0) < 0 ? "text-crit" : "text-pos"}>{num(c.getValue(), 2)}</span> }),
    ch.accessor("net_sharpe_ci95", { header: "Net Sharpe 95% CI", cell: (c) => (c.getValue() ? `${num(c.getValue()[0], 2)} … ${num(c.getValue()[1], 2)}` : "—") }),
    ch.accessor("net_max_drawdown", { header: "Net max DD", cell: (c) => pct(c.getValue(), 1) }),
    ch.accessor("avg_turnover", { header: "Turnover", cell: (c) => pct(c.getValue(), 0) }),
    ch.accessor("avg_cost_bps", { header: "Cost / rebalance", cell: (c) => (c.getValue() == null ? "—" : `${num(c.getValue(), 1)} bp`) }),
    ch.accessor("long_only_net_excess_vs_spy", { header: "Long-only vs SPY (net, p.a.)", cell: (c) => pct(c.getValue(), 1) }),
  ];
  const eq = hr.equity;
  const lo = new Map<string, number>(eq.long_only_net), spy = new Map<string, number>(eq.spy);
  return (
    <div className="space-y-4">
      <PageHeader title="AI Research Lab" subtitle={`${r.universe} · ${r.rows_in_universe.toLocaleString()} rows · costs included`} actions={<DataStatus kind="research" />} />
      <div className="grid gap-3 lg:grid-cols-3">
        <InsightCard value={`0 / ${dec.length}`} tone="warn" title={r.verdict}
          detail={`${rejected} of ${dec.length} model-horizon candidates failed the promotion rules. This is a governance outcome, not a software failure. ${r.survivorship_note}`} />
        <MetricCard title={`Best ${h}-session model by rank IC: ${hr.best_by_ic}`} value={num(best.ic_mean, 4)}
          sub={`t = ${num(best.ic_t, 2)} on non-overlapping dates · top-decile precision ${pct(best.top_decile_precision, 1)} vs 10% base`}
          pill={<Badge tone="warn">not validated</Badge>} />
        <MetricCard title="Gross → net Sharpe (long/short)" value={`${num(best.gross_sharpe, 2)} → ${num(best.net_sharpe, 2)}`}
          sub={`average cost ${num(best.avg_cost_bps, 1)} bp per rebalance · SPY buy-and-hold Sharpe ${num(hr.benchmark_spy.sharpe, 2)}`}
          pill={<Badge tone={best.net_sharpe > 0 ? "good" : "crit"}>after costs</Badge>} />
      </div>
      <Tabs tabs={[{ id: "1", label: "Next day" }, { id: "5", label: "Next 5 sessions" }, { id: "20", label: "Next 20 sessions" }]} value={h} onChange={setH} />
      <Card className="rounded-2xl p-3 text-xs text-muted">
        Train {hr.split.train.start} → {hr.split.train.end} ({hr.split.train.rows.toLocaleString()} rows) · validation {hr.split.validation.start} → {hr.split.validation.end} ·
        untouched holdout {hr.split.holdout.start} → {hr.split.holdout.end} ({hr.split.holdout.rows.toLocaleString()} rows) · embargo {hr.embargo_sessions} sessions · target {hr.target}
      </Card>
      <div className="grid gap-3 lg:grid-cols-2">
        <ChartCard id="model_net_sharpe" title={`Net Sharpe after costs, ${h}-session horizon (holdout)`} subtitle="Hatched bar: best model by rank IC" csvHeader={CSV_RES}
          rows={traded.map((m) => ({ model: m.name, gross_sharpe: m.gross_sharpe, net_sharpe: m.net_sharpe }))}>
          <GlossyBars categories={traded.map((m) => m.name)} values={traded.map((m) => +m.net_sharpe.toFixed(2))} highlight={traded.findIndex((m) => m.name === hr.best_by_ic)}
            unitFmt={(v) => num(v, 2)} ariaLabel={`Net Sharpe by model, ${h}-session horizon`} />
        </ChartCard>
        <ChartCard id="model_holdout_equity" title={`Holdout growth of 1, ${eq.model}`} subtitle="Net long/short (hero) vs gross, long-only top decile and SPY" csvHeader={CSV_RES}
          option={heroLineOption(eq.net.map((x: [string, number]) => x[0]), [
            { name: "Long/short net", hero: true, values: eq.net.map((x: [string, number]) => x[1]) },
            { name: "Long/short gross", dashed: true, values: eq.gross.map((x: [string, number]) => x[1]) },
            { name: "Long-only net", values: eq.net.map((x: [string, number]) => lo.get(x[0]) ?? null) },
            { name: "SPY", values: eq.net.map((x: [string, number]) => spy.get(x[0]) ?? null) },
          ], (v) => num(v, 2))} height={280} rows={eq.net.map((x: [string, number]) => ({ date: x[0], net: x[1] }))} />
      </div>
      <DataTable label={`Models, ${h}-session horizon`} data={models} columns={cols} search={false} />
      <Card className="rounded-2xl p-4">
        <h3 className="mb-2 text-sm font-semibold">Promotion decisions</h3>
        <ul className="space-y-2 text-sm">{hr.decisions.map((d: any) => (
          <li key={d.model}><Badge tone={d.eligible ? "good" : "crit"}>{d.status.replace(/_/g, " ")}</Badge> <span className="font-medium">{d.model}</span>
            <span className="text-muted"> — {d.reasons.join("; ") || "all criteria met"}</span></li>))}</ul>
      </Card>
      <ExplorePrompt suggestions={["Why did the model reject this opportunity?", "Show Prediction Memory.", "Which datasets are available?"]} />
    </div>
  );
}
