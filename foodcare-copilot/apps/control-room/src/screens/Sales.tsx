import { useState } from "react";
import { ChartCard, DivergingBars, HBars, LineChart } from "../components/charts";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";
import { money, pct } from "./Executive";

const PROVINCES = ["", "ON", "QC", "BC", "AB", "MB", "NS"];
const CHANNELS = ["", "retail", "web", "marketplace"];

export default function Sales() {
  const [weeks, setWeeks] = useState(4);
  const [province, setProvince] = useState("");
  const [channel, setChannel] = useState("");
  const qs = new URLSearchParams({ weeks: String(weeks), ...(province && { province }), ...(channel && { channel }) });
  const sales = usePoll<any>(`/api/enterprise/sales?${qs}`, 15000);
  const camps = usePoll<any>("/api/enterprise/campaigns", 10000);
  const s = sales.data;
  const c = camps.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Sales and promotions</h1>
          <p className="text-sm text-navy-600">Synthetic weekly sales by product, region and channel, plus live orders from the demo storefront.</p>
        </div>
        <AskButton question="How did past promotions perform?" label="Ask about promotions" />
      </div>
      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-cream-300 bg-white px-3 py-2 text-sm" role="group" aria-label="Filters">
        <label>Window <select className="ml-1 rounded border border-cream-300 px-1" value={weeks} onChange={(e) => setWeeks(Number(e.target.value))}>{[1, 2, 4, 8].map((w) => <option key={w} value={w}>last {w} week{w > 1 ? "s" : ""}</option>)}</select></label>
        <label>Region <select className="ml-1 rounded border border-cream-300 px-1" value={province} onChange={(e) => setProvince(e.target.value)}>{PROVINCES.map((p) => <option key={p} value={p}>{p || "All"}</option>)}</select></label>
        <label>Channel <select className="ml-1 rounded border border-cream-300 px-1" value={channel} onChange={(e) => setChannel(e.target.value)}>{CHANNELS.map((p) => <option key={p} value={p}>{p || "All"}</option>)}</select></label>
      </div>
      {sales.error && <Notice kind="error">{sales.error}</Notice>}
      {!s ? <Empty>Loading…</Empty> : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card><div className="text-xs text-navy-600">Revenue ({s.current_weeks[0]} to {s.current_weeks[1]})</div><div className="text-2xl font-semibold">{money(s.revenue_cents)}</div><div className="text-xs text-navy-600">{pct(s.revenue_change_pct)} vs previous {s.window_weeks} week(s)</div></Card>
            <Card><div className="text-xs text-navy-600">Units</div><div className="text-2xl font-semibold">{s.units.toLocaleString()}</div><div className="text-xs text-navy-600">{pct(s.units_change_pct)} vs previous {s.window_weeks} week(s)</div></Card>
            <Card><div className="text-xs text-navy-600">Scope</div><div className="text-sm font-semibold">{s.scope}</div></Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <ChartCard title={`Weekly revenue, ${s.scope}`} subtitle="All 16 weeks of synthetic history"
                table={<table className="table"><tbody>{s.trend.map((t: any) => <tr key={t.week_start}><td>{t.week_start}</td><td>{money(t.revenue)}</td></tr>)}</tbody></table>}>
                <LineChart points={s.trend.map((t: any) => ({ label: t.week_start, value: t.revenue }))} format={money} ariaLabel="Weekly revenue trend for the selected scope" />
              </ChartCard>
            </div>
            <ChartCard title="Revenue by product" subtitle={`Last ${s.window_weeks} week(s)`}
              table={<table className="table"><tbody>{s.by_sku.map((r: any) => <tr key={r.sku}><td>{r.name}</td><td>{money(r.revenue)}</td><td>{r.units.toLocaleString()}</td></tr>)}</tbody></table>}>
              <HBars items={s.by_sku.map((r: any) => ({ label: r.name.replace("FreshSip ", ""), value: r.revenue }))} format={money} ariaLabel="Revenue by product" />
            </ChartCard>
          </div>
        </>
      )}
      {c && (
        <div className="grid gap-4 lg:grid-cols-2">
          <ChartCard title="Promotion uplift in units" subtitle="Campaign weeks vs the 4 weeks before, promoted SKUs in the campaign region"
            table={<table className="table"><thead><tr><th>Campaign</th><th>Units</th><th>Revenue</th><th>Method</th></tr></thead><tbody>{c.campaigns.map((x: any) => <tr key={x.id}><td>{x.name}</td><td>{pct(x.unit_uplift_pct)}</td><td>{pct(x.revenue_change_pct)}</td><td className="text-xs">{x.method}</td></tr>)}</tbody></table>}>
            <DivergingBars ariaLabel="Unit uplift by campaign" items={c.campaigns.map((x: any) => ({ label: x.name, value: x.unit_uplift_pct, sub: `${x.region} · ${x.mechanic}` }))} />
          </ChartCard>
          <ChartCard title="Promotion effect on revenue" subtitle="Discounts can grow units while shrinking revenue"
            table={<table className="table"><tbody>{c.campaigns.map((x: any) => <tr key={x.id}><td>{x.name}</td><td>{pct(x.revenue_change_pct)}</td></tr>)}</tbody></table>}>
            <DivergingBars ariaLabel="Revenue change by campaign" items={c.campaigns.map((x: any) => ({ label: x.name, value: x.revenue_change_pct, sub: `${x.start} to ${x.end}` }))} />
          </ChartCard>
          <Card title="Ontario weekend campaign: live storefront orders">
            {!c.live_storefront.available || !c.live_storefront.orders ? <Empty>No orders on the demo storefront yet. Run the guided demo or place an order in the storefront.</Empty> : (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <dt className="text-navy-600">Paid orders</dt><dd>{c.live_storefront.paid_orders}</dd>
                <dt className="text-navy-600">Customers</dt><dd>{c.live_storefront.customers}</dd>
                <dt className="text-navy-600">Units (free)</dt><dd>{c.live_storefront.units} ({c.live_storefront.free_units})</dd>
                <dt className="text-navy-600">Committed redemptions</dt><dd>{c.live_storefront.redemptions}</dd>
                <dt className="text-navy-600">Order value</dt><dd>{money(c.live_storefront.revenue_cents)}</dd>
                <dt className="text-navy-600">Refunded</dt><dd>{money(c.live_storefront.refunded_cents)}</dd>
              </dl>
            )}
            <p className="mt-2 text-xs text-navy-600">These are real orders on the local demo storefront (mostly guided-demo traffic), not synthetic history.</p>
          </Card>
          <Card title="Campaign stock risk (DC-TOR)">
            <table className="table">
              <thead><tr><th>Product</th><th>Weekend forecast</th><th>Projected at start</th><th>Risk</th></tr></thead>
              <tbody>{c.stock_risk.lines.map((l: any) => <tr key={l.sku}><td>{l.name}</td><td>{l.weekend_forecast_units.toLocaleString()}</td><td>{l.stockout_before_start ? "stock-out" : l.projected_at_start.toLocaleString()}</td><td className={l.risk === "high" ? "font-semibold text-brick-700" : ""}>{l.risk}</td></tr>)}</tbody>
            </table>
            <ul className="mt-2 list-disc pl-5 text-xs text-navy-600">{c.stock_risk.assumptions.map((a: string) => <li key={a}>{a}</li>)}</ul>
          </Card>
        </div>
      )}
    </div>
  );
}
