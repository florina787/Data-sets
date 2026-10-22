import { Crown, Lightbulb } from "lucide-react";
import { useState } from "react";
import { Badge, Card, CardHeader, PageHeader } from "@/components/common/ui";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { AskButton, Chart, DashboardShell, useDashboard, WindowSelect } from "@/components/dashboard/Dashboard";
import { RelationGraph } from "@/components/workflow/RelationGraph";
import { pct } from "@/lib/format";
import type { Recommendation } from "@/types/api";

export default function Leadership() {
  const [win, setWin] = useState("all");
  const { data, loading, error, reload } = useDashboard("leadership", win);
  const { openConversation } = useEvidence();
  const lp = data?.results.leadership_priorities;
  const recs = (lp?.series.recommendations?.rows ?? []) as Recommendation[];
  const top = lp?.table?.rows[0];
  return (
    <DashboardShell loading={loading} error={error} reload={reload}
      header={<PageHeader title="Leadership Command Center" icon={<Crown className="h-5 w-5" />}
        subtitle="Recurring concerns ranked by a transparent, configurable priority score — with evidence, owners and uncertainty."
        actions={<div className="flex gap-2"><WindowSelect value={win} onChange={setWin} /><AskButton question="Which recurring customer concerns should contact-centre leadership review first?" /></div>} />}>
      {data && lp && (
        <div className="space-y-5">
          <Card className="overflow-hidden">
            <div className="grid gap-0 lg:grid-cols-[1.3fr_1fr]">
              <div className="border-b border-line p-5 lg:border-b-0 lg:border-r">
                <p className="label">Executive summary · {data.scope.window.label}</p>
                <p className="mt-2 text-lg font-semibold leading-snug">Review <span className="text-cyan">{top?.name}</span> first (priority {top?.priority_score}), then {recs.slice(1, 3).map((r) => r.concern).join(" and ")}.</p>
                <p className="mt-2 text-sm text-muted">{recs[0]?.finding}</p>
                <p className="mt-2 text-xs text-faint">{lp.uncertainty_notes.join(" ")}</p>
              </div>
              <div className="p-5">
                <p className="label mb-2">Score weights (documented, configurable)</p>
                <ul className="space-y-1.5">
                  {lp.series.weights.rows.map((w) => (
                    <li key={w.signal} className="flex items-center gap-2 text-xs">
                      <span className="w-40 shrink-0 text-muted">{w.label}</span>
                      <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/5"><span className="block h-full rounded-full bg-gradient-to-r from-indigo to-cyan" style={{ width: `${w.weight * 100 / 0.3}%` }} /></span>
                      <span className="num w-10 text-right text-ink">{w.weight.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Card>
          <Chart d={data} id="_lead_kpis" />
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart d={data} id="priority_matrix" />
            <Chart d={data} id="priority_scores" />
          </div>
          <section>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold"><Lightbulb className="h-4 w-4 text-mix" />Recommended next actions <span className="text-xs font-normal text-faint">human decision owner required</span></h2>
            <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
              {recs.map((r) => (
                <div key={r.topic} className="rounded-xl border border-line bg-surface/70 p-4">
                  <div className="flex items-center justify-between"><p className="text-sm font-semibold">#{r.rank} {r.concern}</p>
                    <Badge tone={r.priority === "High" ? "negative" : r.priority === "Medium" ? "warning" : "indigo"}>{r.priority}</Badge></div>
                  <p className="mt-2 text-xs text-muted">{r.finding}</p>
                  <p className="mt-2 text-xs text-ink"><span className="text-faint">Action:</span> {r.suggested_action}</p>
                  <p className="mt-1 text-xs text-ink"><span className="text-faint">Owner:</span> {r.decision_owner} · <span className="text-faint">Driver:</span> {r.supporting_metric.label} {r.supporting_metric.value <= 1 ? pct(r.supporting_metric.value) : r.supporting_metric.value}</p>
                  <div className="mt-2 flex flex-wrap gap-1">{r.evidence.map((id) => <button key={id} onClick={() => openConversation(id)} className="focus-ring rounded border border-line px-1.5 font-mono text-[10px] text-cyan hover:bg-white/5">{id}</button>)}</div>
                </div>
              ))}
            </div>
          </section>
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart d={data} id="sentiment_trend" />
            <Chart d={data} id="resolution_misfit" />
          </div>
          {data.graphs.map((g) => <RelationGraph key={g.graph_id} spec={g} />)}
          <div className="grid gap-4 xl:grid-cols-2">
            <Chart d={data} id="sensitivity" />
            <Card><CardHeader title="What this score cannot tell you" subtitle="Signals not present in the dataset" />
              <ul className="space-y-1.5 px-5 pb-5 pt-3 text-xs text-muted">
                <li>• Financial impact, churn, repeat contact and handle time are not in the data and are not estimated.</li>
                <li>• Min-max scaling stretches small differences; adjacent ranks with close scores should be treated as ties.</li>
                <li>• Closing-action misfit uses a documented issue→action mapping (see ASSUMPTIONS.md).</li>
              </ul></Card>
          </div>
        </div>
      )}
    </DashboardShell>
  );
}
