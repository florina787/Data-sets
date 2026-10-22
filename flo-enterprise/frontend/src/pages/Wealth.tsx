import { useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorState, PageHeader, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { baseOption, tokens } from "@/lib/chartTheme";
import { cad } from "@/lib/format";

const ch = createColumnHelper<any>();

export default function Wealth() {
  const nav = useNavigate();
  const home = useQuery({ queryKey: ["whome"], queryFn: () => api("/api/wealth/home") });
  const dir = useQuery({ queryKey: ["wdir"], queryFn: () => api("/api/wealth/clients") });
  const tk = tokens();
  const h = home.data;
  const segOpt = useMemo(() => h && ({ ...baseOption(), legend: { ...baseOption().legend, bottom: 0, top: "auto" },
    series: [{ type: "pie", radius: ["50%", "75%"], itemStyle: { borderColor: tk.surface, borderWidth: 2 }, label: { color: tk.ink, formatter: "{b}: {c}" },
      data: Object.entries(h.segments).map(([k, v]) => ({ name: k, value: v })) }] }), [h, tk]);
  const cols = [ch.accessor("id", { header: "Client" }), ch.accessor("name", { header: "Name" }), ch.accessor("segment", { header: "Segment" }),
    ch.accessor("risk_profile", { header: "Risk profile" }), ch.accessor("assets_with_flo", { header: "Assets with FLO", cell: (c) => cad(c.getValue()) }),
    ch.accessor("portfolios", { header: "Portfolios" }), ch.accessor("language", { header: "Lang" }), ch.accessor("kyc_last_review", { header: "KYC review" }),
    ch.accessor("status", { header: "Status", cell: (c) => <Badge tone={c.getValue() === "active" ? "good" : "neutral"}>{c.getValue()}</Badge> })];
  if (home.error) return <ErrorState error={home.error} />;
  return (
    <div className="space-y-4">
      <PageHeader title="Wealth Advisor 360 — Advisor Home" subtitle="Only clients assigned to you are visible (resource-level authorization). Private wealth records are segregated from product research." />
      {!h ? <Spinner /> : (
        <div className="grid gap-3 md:grid-cols-4">
          <Stat label="Active clients" value={h.active_clients} /><Stat label="Book assets" value={cad(h.book_aum)} />
          <Stat label="KYC due within 60 days or overdue" value={h.kyc_due.length} tone={h.kyc_due.length ? "warn" : "good"} />
          <Stat label="Interaction sentiment" value={`${h.sentiment.negative} negative`} sub={`${h.sentiment.positive} positive · ${h.sentiment.neutral} neutral`} />
        </div>
      )}
      {h && (
        <div className="grid gap-4 xl:grid-cols-3">
          <ChartCard id="timeline" title="Book by segment" option={segOpt} height={220} rows={Object.entries(h.segments).map(([k, v]) => ({ segment: k, clients: v as number }))} />
          <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Follow-ups</h3><ul className="space-y-1 text-xs">
            {h.follow_ups.map((f: any, i: number) => <li key={i}><button className="hover:text-gold text-left" onClick={() => nav(`/wealth/clients/${f.client_id}`)}>{f.ts.slice(0, 10)} · {f.name} — {f.topic} ({f.channel})</button></li>)}</ul></Card>
          <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">KYC refresh queue</h3><ul className="space-y-1 text-xs">
            {h.kyc_due.map((k: any) => <li key={k.client_id}><button className="hover:text-gold text-left" onClick={() => nav(`/wealth/clients/${k.client_id}`)}>{k.name} — last review {k.kyc_last_review} ({k.days} days)</button></li>)}</ul></Card>
        </div>
      )}
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Client directory</h3>
        {dir.isLoading ? <Spinner /> : dir.error ? <ErrorState error={dir.error} /> : <DataTable label="Clients" data={dir.data.clients} columns={cols} onRowClick={(r: any) => nav(`/wealth/clients/${r.id}`)} />}
      </Card>
    </div>
  );
}
