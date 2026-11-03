import { useState } from "react";
import { Plot } from "../components/Plot";
import { Badge, Card, ChartCard, DataClassBadge, Note, PageHeader, Spinner, Table } from "../components/ui";
import { InvestmentGraph } from "../components/InvestmentGraph";
import { useApi } from "../lib/api";
import { AGENT_COLORS, money } from "../lib/format";

export default function Portfolio() {
  const list = useApi<any[]>("/portfolios");
  const [pid, setPid] = useState("PF-BAL");
  const p = useApi<any>(`/portfolios/${pid}`);
  return (
    <div>
      <PageHeader title="Portfolio Dashboard" subtitle="Holdings, exposures and transactions. Assets under management are never counted as bank revenue." />
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        {(list.data ?? []).map((x) => (
          <button key={x.id} type="button" onClick={() => setPid(x.id)} className={`card p-4 text-left transition ${pid === x.id ? "ring-2 ring-flo-600" : "hover:-translate-y-0.5"}`}>
            <div className="text-xs font-semibold uppercase tracking-wide text-muted">{x.id} · {x.manager}</div>
            <div className="font-display text-lg font-semibold text-flo-900">{x.name}</div>
            <div className="font-display text-2xl font-semibold text-flo-800 tnum">{money(x.nav_usd)}</div>
            <div className="mt-1 flex gap-1"><Badge tone="slate">AUM · not revenue</Badge><DataClassBadge dc={x.data_class} /></div>
          </button>))}
      </div>
      {!p.data ? <Spinner /> : (
        <div className="grid gap-4 xl:grid-cols-2">
          <ChartCard title="Sector allocation" subtitle={`${p.data.name} · NAV ${money(p.data.nav_usd)}`}>
            <Plot ariaLabel="Sector allocation" height={380} data={[{ type: "pie", hole: 0.55, labels: Object.keys(group(p.data.positions)), values: Object.values(group(p.data.positions)), marker: { colors: AGENT_COLORS } }]}
              layout={{ showlegend: true, legend: { orientation: "v", x: 1, y: 0.5 }, margin: { l: 8, r: 8, t: 8, b: 8 } }} />
          </ChartCard>
          <ChartCard title="Mandate" subtitle="Limits enforced by Sherin Guardian before any trade">
            <Table dense columns={[{ key: "k", label: "Control" }, { key: "v", label: "Limit" }]} rows={Object.entries(p.data.mandate).map(([k, v]) => ({ k: k.replace(/_/g, " "), v: Array.isArray(v) ? v.join(", ") || "none" : String(v) }))} />
          </ChartCard>
          <ChartCard title="Positions" className="xl:col-span-2">
            <Table dense columns={[{ key: "issuer", label: "Issuer" }, { key: "sector", label: "Sector" }, { key: "asset_class", label: "Class" }, { key: "rating", label: "Rating" },
              { key: "esg_score", label: "ESG", align: "right" }, { key: "liquidity_days", label: "Liq. days", align: "right" }, { key: "weight_pct", label: "Weight %", align: "right" },
              { key: "mv", label: "Market value", align: "right", render: (r) => money(r.market_value_usd) }]} rows={p.data.positions} />
          </ChartCard>
          <ChartCard title="Recent transactions"><Table dense columns={[{ key: "date", label: "Date" }, { key: "issuer", label: "Issuer" }, { key: "side", label: "Side" }, { key: "n", label: "Notional", align: "right", render: (r) => money(r.notional_usd) }]} rows={p.data.transactions} /></ChartCard>
          <Card className="p-5"><h2 className="mb-2 font-display text-xl font-semibold text-flo-900">Investment web graph</h2><InvestmentGraph height={420} /><Note>Click a proposal to open it in the Investment Judgment Center.</Note></Card>
        </div>
      )}
    </div>
  );
}
function group(pos: any[]) { const g: Record<string, number> = {}; pos.forEach((p) => (g[p.sector] = (g[p.sector] ?? 0) + p.market_value_usd)); return g; }
