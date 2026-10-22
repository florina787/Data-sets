import { useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { cad, compact, pct } from "@/lib/format";

const ch = createColumnHelper<any>();

export default function Products() {
  const funds = useQuery({ queryKey: ["funds"], queryFn: () => api("/api/investment/funds") });
  const [sel, setSel] = useState<string[]>([]);
  const cmp = useQuery({ queryKey: ["cmp", sel], queryFn: () => api(`/api/wealth/products/compare?ids=${sel.join(",")}`), enabled: sel.length > 0 });
  const tk = tokens();
  const opt = useMemo(() => cmp.data && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => cad(v) },
    xAxis: axis({ type: "category", data: cmp.data.products.map((p: any) => `${p.id} (${p.fee_bps} bps)`) }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
    series: [{ name: "Ending value after fees", type: "bar", stack: "v", data: cmp.data.products.map((p: any) => p.fee_impact.ending_with_fee), itemStyle: { color: tk.series[0] } },
      { name: "Fee drag", type: "bar", stack: "v", data: cmp.data.products.map((p: any) => p.fee_impact.fee_drag), itemStyle: { color: tk.series[1], borderRadius: [4, 4, 0, 0] } }] }), [cmp.data, tk]);
  const toggle = (id: string) => setSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id].slice(-6)));
  const cols = [ch.display({ id: "pick", header: "Compare", cell: (c) => <input type="checkbox" aria-label={`Compare ${c.row.original.name}`} checked={sel.includes(c.row.original.id)} onChange={() => toggle(c.row.original.id)} onClick={(e) => e.stopPropagation()} /> }),
    ch.accessor("name", { header: "Product" }), ch.accessor("vehicle", { header: "Vehicle" }), ch.accessor("strategy", { header: "Strategy" }), ch.accessor("risk_rating", { header: "Risk" }),
    ch.accessor("fee_bps", { header: "Fee (bps)" }), ch.accessor("return_12m", { header: "12m return", cell: (c) => pct(c.getValue()) }), ch.accessor("volatility", { header: "Vol", cell: (c) => pct(c.getValue()) })];
  return (
    <div className="space-y-4">
      <PageHeader title="Product Research" subtitle="Public product information for internal and external advisors. Contains no client records; not a recommendation." />
      <Card className="p-3 text-xs text-muted"><Badge tone="blue">general information</Badge> Fee impact assumes a 6% gross annual return on CAD 100,000 over 10 years (illustrative).</Card>
      {sel.length > 0 && <ChartCard id="fee_comparison" title="Fee comparison — ending value and fee drag" option={opt} loading={cmp.isLoading} error={cmp.error} lineage={funds.data?.lineage}
        rows={cmp.data?.products.map((p: any) => ({ product: p.name, fee_bps: p.fee_bps, ending_with_fee: p.fee_impact.ending_with_fee, fee_drag: p.fee_impact.fee_drag }))} />}
      {funds.isLoading ? <Spinner /> : funds.error ? <ErrorState error={funds.error} /> : <DataTable label="Products" data={funds.data.data.funds} columns={cols} onRowClick={(r: any) => toggle(r.id)} />}
    </div>
  );
}
