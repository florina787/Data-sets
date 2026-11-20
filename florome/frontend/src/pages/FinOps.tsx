import { useMemo, useState } from "react";
import { Chart, type ChartOption } from "../components/Chart";
import { Page } from "../components/Layout";
import { Card, DemoLabel, ErrorBox, Loading, SectionTitle, Stat } from "../components/ui";
import { api } from "../lib/api";
import { money } from "../lib/format";
import { useAsync } from "../lib/useAsync";

interface Costs { period: string | null; periods: string[]; currency: string; is_demo: boolean; note: string; totals_by_period: { period: string; amount: number }[]; sankey: { nodes: { name: string }[]; links: { source: string; target: string; value: number }[] } }
const LEVEL_COLOR: Record<string, string> = { provider: "#14164A", account: "#3B3DAA", bu: "#5B63E6", app: "#7C84F2", ai: "#A3AAFB", outcome: "#1F9D6B" };

export default function FinOps() {
  const [period, setPeriod] = useState<string | null>(null);
  const costs = useAsync(() => api<Costs>(`/finops/costs${period ? `?period=${period}` : ""}`), [period]);
  const [focus, setFocus] = useState<string | null>(null);
  const d = costs.data;

  const option: ChartOption | null = useMemo(() => {
    if (!d) return null;
    const touches = (l: { source: string; target: string }) => !focus || l.source === focus || l.target === focus;
    return {
      tooltip: { trigger: "item", formatter: (p: { data: { source?: string; target?: string; value?: number; name?: string } }) =>
        p.data.source ? `${p.data.source.split(":")[1]} → ${p.data.target!.split(":")[1]}<br/>${money(p.data.value!)}` : p.data.name?.split(":")[1] ?? "" },
      series: [{
        type: "sankey", left: 10, right: 160, nodeGap: 10, emphasis: { focus: "adjacency" },
        label: { formatter: (p: { name: string }) => p.name.split(":")[1], color: "#0E1024", fontSize: 11 },
        data: d.sankey.nodes.map((n) => ({ name: n.name, itemStyle: { color: LEVEL_COLOR[n.name.split(":")[0]] } })),
        links: d.sankey.links.map((l) => ({ ...l, lineStyle: { color: "gradient", opacity: touches(l) ? 0.45 : 0.06 } })),
      }],
    };
  }, [d, focus]);

  return (
    <Page>
      <SectionTitle eyebrow="FinOps intelligence" title="The AI money river" sub="Spend traced from cloud provider to account, business unit, application, AI component and the business outcome it serves. Click a node to isolate its flows." />
      {costs.error && <ErrorBox error={costs.error} />}
      {costs.loading && <Loading />}
      {d && (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            {d.periods.map((p) => <button key={p} onClick={() => setPeriod(p)} className={`rounded-full border px-3 py-1 text-xs ${p === d.period ? "border-ink bg-ink text-white" : "border-dome-100 bg-white"}`}>{p}</button>)}
            {focus && <button onClick={() => setFocus(null)} className="text-xs text-dome-600 underline">clear focus ({focus.split(":")[1]})</button>}
            {d.is_demo && <DemoLabel className="ml-auto" />}
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {d.totals_by_period.map((t, i) => (
              <Card key={t.period}><Stat label={t.period} value={money(t.amount)} sub={i > 0 ? `${(((t.amount - d.totals_by_period[i - 1].amount) / d.totals_by_period[i - 1].amount) * 100).toFixed(1)}% month on month` : "baseline"} /></Card>
            ))}
          </div>
          <Card className="mt-4">{option && <Chart option={option} height={520} label="Sankey of spend by provider, account, unit, application, AI component and outcome" onClick={(p) => { if (p.name && !(p.data as { source?: string })?.source) setFocus(p.name === focus ? null : p.name); }} />}</Card>
          <p className="mt-2 text-xs text-ink-mute">{d.note} Values are records, not estimates; no ROI is computed here.</p>
        </>
      )}
    </Page>
  );
}
