import { useState } from "react";
import { ChartCard, CoverBars, StatusBadge } from "../components/charts";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";

export default function Inventory() {
  const [warehouse, setWarehouse] = useState("");
  const { data, error } = usePoll<any>(`/api/enterprise/inventory${warehouse ? `?warehouse=${warehouse}` : ""}`, 10000);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Inventory</h1>
          <p className="text-sm text-navy-600">Distribution-centre stock, days of cover and inbound purchase orders (synthetic), plus the live e-commerce allocation.</p>
        </div>
        <AskButton question="Is there enough apple stock for the Ontario weekend campaign?" label="Ask about campaign stock" />
      </div>
      <div className="flex items-center gap-2 rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm" role="group" aria-label="Filters">
        <label>Warehouse <select className="ml-1 rounded border border-cream-300 px-1" value={warehouse} onChange={(e) => setWarehouse(e.target.value)}>
          <option value="">All</option><option value="DC-TOR">DC-TOR Toronto</option><option value="DC-MTL">DC-MTL Montreal</option><option value="DC-VAN">DC-VAN Vancouver</option>
        </select></label>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? <Empty>Loading…</Empty> : (
        <>
          <ChartCard title={`Days of cover, as of ${data.as_of}`} subtitle="Bar = days of cover; black tick = supplier lead time. Below the tick means stock runs out before a new order could arrive."
            table={<table className="table"><thead><tr><th>Warehouse</th><th>Product</th><th>On hand</th><th>Daily demand</th><th>Cover (days)</th><th>Lead time</th><th>Reorder point</th><th>Status</th><th>Inbound</th></tr></thead>
              <tbody>{data.items.map((i: any) => <tr key={i.warehouse + i.sku}><td>{i.warehouse}</td><td>{i.name}</td><td>{i.on_hand.toLocaleString()}</td><td>{i.avg_daily_demand}</td><td>{i.days_of_cover}</td><td>{i.lead_time_days}</td><td>{i.reorder_point.toLocaleString()}</td><td><StatusBadge status={i.status} /></td><td className="text-xs">{i.inbound.map((x: any) => `${x.po} ${x.units} ETA ${x.eta}`).join(", ") || "-"}</td></tr>)}</tbody></table>}>
            <CoverBars items={data.items.map((i: any) => ({ label: `${i.warehouse} · ${i.name.replace("FreshSip ", "")}`, cover: i.days_of_cover, lead: i.lead_time_days, status: i.status }))} />
          </ChartCard>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title={`Alerts (${data.alerts.length})`}>
              {data.alerts.length === 0 ? <Empty>No alerts.</Empty> : (
                <ul className="space-y-1 text-sm">{data.alerts.map((a: any) => (
                  <li key={a.warehouse + a.sku}><StatusBadge status={a.status} /> {a.name} at {a.warehouse}: {a.on_hand.toLocaleString()} on hand, {a.days_of_cover} days of cover{a.inbound.length ? `; inbound ${a.inbound.map((x: any) => `${x.po} ETA ${x.eta}`).join(", ")}` : "; no inbound order"}</li>
                ))}</ul>
              )}
              <p className="mt-2 text-xs text-navy-600">Method: {data.method}.</p>
            </Card>
            <Card title="E-commerce allocation (live inventory simulator)">
              <table className="table"><tbody>{data.ecommerce_allocation.map((x: any) => <tr key={x.sku}><td className="font-mono text-xs">{x.sku}</td><td>{x.stock}</td></tr>)}</tbody></table>
              <p className="mt-2 text-xs text-navy-600">Stock reserved and committed by real storefront checkouts. The demo fault switch slows this system down.</p>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
