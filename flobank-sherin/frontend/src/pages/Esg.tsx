import { Plot } from "../components/Plot";
import { Badge, ChartCard, DataClassBadge, PageHeader, Spinner, Table } from "../components/ui";
import { useApi } from "../lib/api";
import { SERIES } from "../lib/format";

export default function Esg() {
  const ev = useApi<any>("/compliance/events");
  const grn = useApi<any>("/portfolios/PF-GRN");
  const bal = useApi<any>("/portfolios/PF-BAL");
  const props = useApi<any[]>("/guardian/proposals");
  const byType = ev.data ? Object.entries(ev.data.summary.by_type) as [string, any][] : [];
  return (
    <div>
      <PageHeader title="ESG and Compliance" subtitle="ESG validation of holdings and proposals, exclusions and compliance events." />
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title="ESG scores by holding" subtitle="Green Income Fund requires ≥ 65; Balanced Growth requires ≥ 40" badges={<DataClassBadge dc="synthetic" />}>
          {grn.data && bal.data ? <Plot ariaLabel="ESG scores" height={420} data={[grn.data, bal.data].map((p: any, i: number) => ({ type: "bar", name: p.name, orientation: "h",
            y: p.positions.filter((x: any) => x.esg_score !== null).map((x: any) => x.issuer), x: p.positions.filter((x: any) => x.esg_score !== null).map((x: any) => x.esg_score), marker: { color: i ? SERIES.opex : SERIES.revenue } }))}
            layout={{ barmode: "group", margin: { l: 190, r: 16, t: 8, b: 32 }, hovermode: "closest", shapes: [65, 40].map((x, i) => ({ type: "line", x0: x, x1: x, yref: "paper", y0: 0, y1: 1, line: { color: i ? "#7C8C99" : "#B4413C", dash: "dot" } })) }} /> : <Spinner />}
        </ChartCard>
        <ChartCard title="Compliance events by type" badges={<DataClassBadge dc="synthetic" />}>
          {ev.data ? <Plot ariaLabel="Compliance events" height={420} data={[{ type: "bar", name: "Open", x: byType.map(([k]) => k), y: byType.map(([, v]) => v.open), marker: { color: SERIES.cost } }, { type: "bar", name: "Closed", x: byType.map(([k]) => k), y: byType.map(([, v]) => v.closed), marker: { color: SERIES.revenue } }]}
            layout={{ barmode: "stack", xaxis: { tickangle: -20 } }} /> : <Spinner />}
        </ChartCard>
        <ChartCard title="Proposals with ESG or exclusion findings" className="xl:col-span-2">
          <Table dense columns={[{ key: "id", label: "Proposal" }, { key: "issuer", label: "Issuer" }, { key: "sector", label: "Sector" }, { key: "portfolio_id", label: "Portfolio" }, { key: "decision", label: "Guardian", render: (r) => <Badge tone={r.decision === "BLOCK" ? "red" : r.decision === "PASS" ? "green" : "amber"}>{r.decision}</Badge> }]} rows={props.data ?? []} />
        </ChartCard>
        <ChartCard title="Recent compliance events" className="xl:col-span-2">
          <Table dense columns={[{ key: "date", label: "Date" }, { key: "type", label: "Type" }, { key: "severity", label: "Severity" }, { key: "status", label: "Status" }, { key: "description", label: "Description" }]} rows={(ev.data?.events ?? []).slice(0, 25)} />
        </ChartCard>
      </div>
    </div>
  );
}
