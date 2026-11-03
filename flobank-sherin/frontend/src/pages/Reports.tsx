import { Download } from "lucide-react";
import { GraphF, KpiRow } from "../components/charts";
import { Badge, Card, ChartCard, PageHeader, Table } from "../components/ui";
import { reportUrl, useApi } from "../lib/api";
import { periodParams, useApp } from "../lib/store";

export default function Reports() {
  const s = useApp();
  const rec = useApi<any>("/finance/reconciliation", periodParams(s));
  const meta = useApi<any>("/meta");
  return (
    <div>
      <PageHeader title="Executive Reporting" subtitle="Board-ready figures with definitions, reconciliation evidence and downloadable reports.">
        <a href={reportUrl({ ...periodParams(s), format: "md" })} className="inline-flex items-center gap-1.5 rounded-full bg-flo-800 px-4 py-2 text-sm font-semibold text-white"><Download className="h-4 w-4" />Markdown report</a>
        <a href={reportUrl({ ...periodParams(s), format: "csv" })} className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-flo-900"><Download className="h-4 w-4" />CSV</a>
      </PageHeader>
      <KpiRow />
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <ChartCard title="Reconciliation checks" subtitle="Accounting identities recomputed for the selected period">
          <Table dense columns={[{ key: "name", label: "Check" }, { key: "rule", label: "Rule" }, { key: "ok", label: "Result", render: (r) => <Badge tone={r.ok ? "green" : "red"}>{r.ok ? "pass" : "fail"}</Badge> }]} rows={rec.data?.checks ?? []} />
        </ChartCard>
        <Card className="p-5"><h2 className="font-display text-xl font-semibold text-flo-900">Definitions</h2>
          <dl className="mt-2 space-y-2 text-sm">{Object.entries(meta.data?.definitions ?? {}).map(([k, v]) => <div key={k}><dt className="font-semibold text-flo-900">{k.replace(/_/g, " ")}</dt><dd className="text-muted">{v as string}</dd></div>)}</dl></Card>
      </div>
      <div className="mt-4"><GraphF /></div>
    </div>
  );
}
