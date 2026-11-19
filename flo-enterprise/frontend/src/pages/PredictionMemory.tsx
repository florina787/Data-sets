import { useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { ShieldCheck, ShieldAlert } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { DataStatus, DotBars, ExplorePrompt, InsightCard, MetricCard, ProgressRows } from "@/components/MarketMetrics";
import { Badge, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { num, pct } from "@/lib/format";

const ch = createColumnHelper<any>();

export default function PredictionMemory() {
  const q = useQuery({ queryKey: ["mkt-ledger"], queryFn: () => api("/api/markets/predictions?limit=200"), retry: false });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const d = q.data;
  const g = d.groups;
  const rp = g["mode:historical_replay"] ?? { n: 0, resolved: 0, accuracy: null, pending: 0 };
  const fw = g["mode:forward"] ?? { n: 0 };
  const regimes = Object.entries(g).filter(([k, v]: [string, any]) => k.startsWith("regime:") && v.resolved) as [string, any][];
  const cols = [
    ch.accessor("ticker", { header: "Ticker" }), ch.accessor("mode", { header: "Mode", cell: (c) => <Badge tone={c.getValue() === "forward" ? "good" : "neutral"}>{c.getValue().replace("_", " ")}</Badge> }),
    ch.accessor("created_at", { header: "Recorded (UTC)", cell: (c) => c.getValue().slice(0, 16) }),
    ch.accessor("outcome_due", { header: "Outcome due", cell: (c) => c.getValue().slice(0, 16) }),
    ch.accessor("predicted_excess_return", { header: "Predicted excess", cell: (c) => pct(c.getValue(), 2) }),
    ch.accessor("predicted_rank_pct", { header: "Rank pct", cell: (c) => pct(c.getValue(), 0) }),
    ch.accessor("uncertainty", { header: "± band (1σ)", cell: (c) => pct(c.getValue(), 1) }),
    ch.accessor((r) => r.outcome?.actual_excess_return, { id: "actual", header: "Actual excess vs SPY", cell: (c) => pct(c.getValue(), 2) }),
    ch.accessor((r) => r.outcome?.direction_correct, { id: "ok", header: "Direction", cell: (c) => (c.getValue() == null ? "—" : c.getValue() ? <span className="text-pos">correct</span> : <span className="text-crit">wrong</span>) }),
    ch.accessor("regime", { header: "Regime", cell: (c) => c.getValue().replace(/_/g, " ") }),
  ];
  return (
    <div className="space-y-4">
      <PageHeader title="Prediction Memory" subtitle="Append-only, hash-chained forecast ledger: every forecast written before its outcome, scored after"
        actions={<DataStatus kind="research" />} />
      <Card className="rounded-2xl border-warn/40 p-3 text-sm">{d.note}</Card>
      <div className="grid gap-3 md:grid-cols-4">
        <MetricCard title="Forecasts recorded" value={d.total.toLocaleString()} sub={`${rp.n.toLocaleString()} historical replay · ${fw.n ?? 0} forward`} />
        <MetricCard title="Resolved" value={(rp.resolved ?? 0).toLocaleString()} sub={`${rp.pending ?? 0} pending`}>
          <DotBars values={regimes.map(([, v]) => v.resolved)} label="Resolved forecasts by regime" />
        </MetricCard>
        <MetricCard title="Direction correct vs SPY" value={pct(rp.accuracy, 1)} sub="coin flip = 50%" pill={<Badge tone="warn">replay</Badge>} />
        <MetricCard title="Ledger integrity" value={d.chain.valid ? "Verified" : "BROKEN"} sub={`${d.chain.checked.toLocaleString()} rows hash-checked`}
          pill={d.chain.valid ? <ShieldCheck className="h-5 w-5 text-pos" aria-label="verified" /> : <ShieldAlert className="h-5 w-5 text-crit" aria-label="broken" />} />
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="rounded-2xl p-4 lg:col-span-2">
          <h3 className="mb-3 text-sm font-semibold">Direction correct by market regime at forecast time</h3>
          {regimes.length ? <ProgressRows label="Accuracy by regime" rows={regimes.map(([k, v]) => ({ label: `${k.split(":")[1].replace(/_/g, " ")} (${v.resolved.toLocaleString()})`,
            value: pct(v.accuracy, 1), share: v.accuracy, tone: v.accuracy >= 0.5 ? "lime" : "pink" }))} /> : <p className="text-sm text-muted">No resolved forecasts yet.</p>}
        </Card>
        <InsightCard value={pct(rp.accuracy, 1)} tone="warn" title="Replay accuracy is indistinguishable from a coin flip"
          detail={`Mean absolute error ${pct(rp.mae, 2)} of excess return. Consistent with the research verdict: no validated trading edge.`} />
      </div>
      <DataTable label="Recent ledger rows" data={d.recent} columns={cols} pageSize={25} />
      <p className="text-xs text-muted">Chain head {d.chain.head?.slice(0, 16)}… · rows cannot be updated or deleted (database triggers) · {num(d.total, 0)} rows</p>
      <ExplorePrompt suggestions={["Show model accuracy over the holdout period.", "Why did the model reject this opportunity?"]} />
    </div>
  );
}
