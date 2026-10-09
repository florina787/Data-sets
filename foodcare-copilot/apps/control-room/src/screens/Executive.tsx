import { Link } from "react-router-dom";
import { ChartCard, HBars, LineChart, StatusBadge } from "../components/charts";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";

export const money = (cents: number) => `$${Math.round(cents / 100).toLocaleString()}`;
export const pct = (v: number | null | undefined) => (v == null ? "n/a" : `${v > 0 ? "+" : ""}${v.toFixed(1)}%`);

function Kpi({ label, value, sub, to }: { label: string; value: string; sub?: string; to?: string }) {
  const body = (
    <div className="h-full rounded-xl border border-cream-300 bg-white p-4 shadow-sm">
      <div className="text-xs text-navy-600">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-navy-900">{value}</div>
      {sub && <div className="mt-1 text-xs text-navy-600">{sub}</div>}
    </div>
  );
  return to ? <Link to={to} className="block hover:opacity-90">{body}</Link> : body;
}

export default function Executive() {
  const { data, error } = usePoll<any>("/api/enterprise/overview", 10000);
  const delivery = usePoll<any>("/api/overview", 10000);
  if (error) return <Notice kind="error">{error}</Notice>;
  if (!data) return <Empty>Loading…</Empty>;
  const s = data.sales;
  const critical = data.inventory_alerts.filter((a: any) => a.status === "critical");
  const highRisk = data.campaign_stock_risk.filter((x: any) => x.risk === "high");
  const d = delivery.data;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Executive overview</h1>
          <p className="text-sm text-navy-600">Food Beverage Food Care: sales, supply, compliance and digital delivery in one place.</p>
        </div>
        <AskButton question="Give me a briefing" label="Ask Copilot for a briefing" />
      </div>
      <Notice kind="info">{data.label}</Notice>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi label={`Revenue, last 4 weeks (${s.current_weeks[0]} to ${s.current_weeks[1]})`} value={money(s.revenue_cents)} sub={`${pct(s.revenue_change_pct)} vs prior 4 weeks`} to="/sales" />
        <Kpi label="Units sold, last 4 weeks" value={s.units.toLocaleString()} sub={`${pct(s.units_change_pct)} vs prior 4 weeks`} to="/sales" />
        <Kpi label="Stock alerts" value={String(data.inventory_alerts.length)} sub={`${critical.length} critical`} to="/inventory" />
        <Kpi label="Listing compliance issues" value={String(data.compliance.critical + data.compliance.warnings)} sub={`${data.compliance.critical} critical`} to="/compliance" />
        <Kpi label="Live storefront orders (demo)" value={String(data.live_storefront.paid_orders ?? 0)} sub={data.live_storefront.available ? `${data.live_storefront.free_units} free units given` : "storefront has no orders yet"} to="/sales" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ChartCard title="Weekly revenue, all products and regions" subtitle="Synthetic history, CAD"
            table={<table className="table"><thead><tr><th>Week</th><th>Revenue</th><th>Units</th></tr></thead><tbody>{s.trend.map((t: any) => <tr key={t.week_start}><td>{t.week_start}</td><td>{money(t.revenue)}</td><td>{t.units.toLocaleString()}</td></tr>)}</tbody></table>}>
            <LineChart points={s.trend.map((t: any) => ({ label: t.week_start, value: t.revenue }))} format={money} ariaLabel="Weekly revenue trend" />
          </ChartCard>
        </div>
        <ChartCard title="Revenue by region, last 4 weeks"
          table={<table className="table"><tbody>{s.by_province.map((r: any) => <tr key={r.province}><td>{r.province}</td><td>{money(r.revenue)}</td></tr>)}</tbody></table>}>
          <HBars items={s.by_province.map((r: any) => ({ label: r.province, value: r.revenue }))} format={money} ariaLabel="Revenue by region" />
        </ChartCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Needs attention">
          <ul className="space-y-2 text-sm">
            {highRisk.map((x: any) => (
              <li key={x.sku}><StatusBadge status="critical" /> <b>{x.name}</b> may not cover the Ontario weekend campaign (forecast {x.weekend_forecast_units.toLocaleString()} units, {x.stockout_before_start ? "stock-out before start" : `${x.projected_at_start} projected`}). <Link className="underline" to="/inventory">Inventory</Link></li>
            ))}
            {data.compliance.issues.filter((i: any) => i.severity === "critical").map((i: any) => (
              <li key={i.sku + i.channel + i.rule}><StatusBadge status="critical" /> <b>{i.name}</b> on {i.channel}: {i.detail}. <Link className="underline" to="/compliance">Compliance</Link></li>
            ))}
            {critical.filter((a: any) => !highRisk.some((x: any) => x.sku === a.sku && a.warehouse === "DC-TOR")).map((a: any) => (
              <li key={a.warehouse + a.sku}><StatusBadge status="critical" /> <b>{a.name}</b> at {a.warehouse}: {a.days_of_cover} days of cover, lead time {a.lead_time_days} days.</li>
            ))}
          </ul>
        </Card>
        <Card title="Promotions">
          <ul className="space-y-1 text-sm">
            {data.campaigns.map((c: any) => (
              <li key={c.id} className="flex justify-between gap-2"><span>{c.name} <span className="text-xs text-navy-600">({c.region})</span></span><span className="font-mono">{pct(c.unit_uplift_pct)} units</span></li>
            ))}
            {data.scheduled_campaigns.map((c: any) => (
              <li key={c.id} className="mt-2 rounded bg-leaf-100 px-2 py-1 text-xs text-leaf-700">Scheduled: {c.name}, {c.start} to {c.end}</li>
            ))}
          </ul>
          <Link to="/sales" className="mt-2 inline-block text-xs underline">Sales & promotions</Link>
        </Card>
        <Card title="Digital delivery">
          {!d ? <Empty>Loading…</Empty> : (
            <ul className="space-y-1 text-sm">
              <li>Live storefront release: <b>{d.current_release?.id ?? "-"}</b> ({d.current_release?.kind})</li>
              <li>Delivery runs: {d.runs.length} ({d.runs.filter((r: any) => r.status === "deployed").length} deployed)</li>
              <li>Releases needing attention: {d.blocked_releases.length}</li>
              <li>Open incidents: {d.incidents.length}</li>
              <li className="pt-1"><Link to="/delivery" className="text-xs underline">Delivery overview</Link></li>
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
