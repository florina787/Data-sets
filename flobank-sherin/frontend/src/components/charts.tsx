import { useMemo, useState } from "react";
import { ArrowDownRight, ArrowUpRight, ChevronRight } from "lucide-react";
import { Plot } from "./Plot";
import { BasisBadge, ChartCard, DataClassBadge, Drawer, ErrorBox, Note, Segmented, Spinner, Table, Badge } from "./ui";
import { useApi } from "../lib/api";
import { periodParams, trendParams, useApp } from "../lib/store";
import { AGENT_COLORS, CAT_COLOR, compact, money, num, pctChange, SERIES, shortAgent, wrap } from "../lib/format";

const H = 440; // giant chart height

export function endOfMonth(m: string) {
  const [y, mm] = m.split("-").map(Number);
  return new Date(Date.UTC(y, mm, 0)).toISOString().slice(0, 10);
}

function useParams() {
  const s = useApp();
  return { p: periodParams(s), t: trendParams(s), cur: s.currency, dc: s.dc };
}

// ------------------------------------------------------------------------------------------- KPI cards
export function KpiRow() {
  const { p, cur } = useParams();
  const { data, error, loading } = useApi<any>("/finance/kpis", p);
  const [open, setOpen] = useState<string | null>(null);
  if (error) return <ErrorBox error={error} />;
  if (loading && !data) return <Spinner label="Loading financial KPIs" />;
  if (!data) return null;
  return (
    <>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" data-testid="kpi-row">
        {data.cards.map((c: any, i: number) => <KpiCard key={c.key} c={c} cur={cur} hero={i < 4} onOpen={() => setOpen(c.key)} />)}
      </div>
      <p className="mt-2 text-xs text-muted">
        {data.period.label} vs {data.prior_period.label} · {cur}{data.fx.currency !== "USD" && ` at ${data.fx.rate} (${data.fx.source}, ${data.fx.as_of?.slice(0, 10)})`} ·
        Net AI economic benefit <strong className="text-flo-800">{money(data.net_benefit, cur)}</strong>
      </p>
      <KpiDrawer k={open} onClose={() => setOpen(null)} />
    </>
  );
}

function KpiCard({ c, cur, hero, onOpen }: { c: any; cur: string; hero: boolean; onOpen: () => void }) {
  const val = c.unit === "currency" ? money(c.value, cur) : c.unit === "pct" ? (c.value === null ? "—" : `${c.value.toFixed(1)}%`) : num(c.value);
  const change = c.unit === "pct" ? (c.mom_pts !== null && c.mom_pts !== undefined ? `${c.mom_pts > 0 ? "+" : ""}${c.mom_pts.toFixed(1)} pts` : "—") : pctChange(c.mom_pct);
  const delta = c.unit === "pct" ? c.mom_pts : c.mom_pct;
  const good = delta === null || delta === undefined ? null : (c.good_direction === "down" ? delta < 0 : delta > 0);
  return (
    <button type="button" onClick={onOpen} data-testid={`kpi-${c.key}`} aria-label={`${c.label}: ${val}. Open drill-down`}
      className={`group card relative overflow-hidden p-4 text-left transition hover:-translate-y-0.5 hover:shadow-lg ${hero ? "kpi-hero text-white" : ""}`}>
      <div className="flex items-start justify-between gap-2">
        <span className={`text-[11px] font-semibold uppercase tracking-wider ${hero ? "text-white/85" : "text-muted"}`}>{c.label}</span>
        <ChevronRight className={`h-4 w-4 transition group-hover:translate-x-0.5 ${hero ? "text-flo-200" : "text-flo-600"}`} aria-hidden />
      </div>
      <div className={`mt-1 font-display text-[2rem] font-semibold leading-tight tnum ${hero ? "text-white" : "text-flo-900"}`}>{val}</div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
        <span className={`inline-flex items-center gap-0.5 font-semibold ${good === null ? (hero ? "text-flo-100" : "text-muted") : good ? (hero ? "text-[#9BE7C2]" : "text-flo-700") : (hero ? "text-[#F7C5C1]" : "text-red")}`}>
          {delta !== null && delta !== undefined && (delta > 0 ? <ArrowUpRight className="h-3.5 w-3.5" /> : <ArrowDownRight className="h-3.5 w-3.5" />)}{change} MoM
        </span>
        {c.budget !== null && <span className={hero ? "text-flo-100" : "text-muted"}>{pctChange(c.budget_variance_pct)} vs budget</span>}
      </div>
      <div className="mt-2 flex flex-wrap gap-1">
        <BasisBadge basis={c.basis} />
        {c.data_class === "synthetic" && <Badge tone="gold">synthetic</Badge>}
        {c.sub?.realized_savings !== undefined && <Badge tone="green" title="Booked in budgets; already inside the estimate">{money(c.sub.realized_savings, cur)} realized</Badge>}
        {c.key === "verified_work" && c.sub && <Badge tone="slate">{num(c.sub.human_hours_equivalent)} h equiv.</Badge>}
      </div>
    </button>
  );
}

export function KpiDrawer({ k, onClose }: { k: string | null; onClose: () => void }) {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>(k ? `/finance/kpis/${k}` : null, p);
  const isMoney = k !== "verified_work";
  return (
    <Drawer open={!!k} onClose={onClose} title={data?.label ?? "Drill-down"}>
      {loading || !data ? <Spinner /> : (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2"><DataClassBadge dc={data.data_class} /><Badge>{data.period.start} → {data.period.end}</Badge><Badge>{cur}</Badge></div>
          <p className="text-sm text-muted">{data.definition}</p>
          <Plot ariaLabel={`${data.label} breakdown`} height={320} testId="drill-plot"
            data={[{ type: "bar", orientation: "h", y: data.rows.map((r: any) => r.label), x: data.rows.map((r: any) => r.value),
              marker: { color: data.rows.map((r: any) => (r.value < 0 ? SERIES.cost : SERIES.revenue)) },
              hovertemplate: isMoney ? `%{y}: %{x:,.2f} ${cur}<extra></extra>` : "%{y}: %{x:,}<extra></extra>" }]}
            layout={{ margin: { l: 220, r: 20, t: 8, b: 32 }, yaxis: { autorange: "reversed" }, hovermode: "closest" }} />
          <Table dense columns={[{ key: "label", label: "Line" }, { key: "value", label: isMoney ? `Value (${cur})` : "Value", align: "right", render: (r) => (isMoney ? money(r.value, cur, false) : num(r.value)) },
            ...(data.rows[0]?.method ? [{ key: "method", label: "Attribution method" }] : [])]} rows={data.rows} />
        </div>
      )}
    </Drawer>
  );
}

// ------------------------------------------------------------------------------------------- Graph A
export function GraphA() {
  const { t, cur } = useParams();
  const [g, setG] = useState("month");
  const meta = useApi<any>("/meta");
  const start = meta.data?.bounds?.[t.dc]?.ledger_start;
  // Day/week/month: trailing 12 months. Quarter/year: the full ledger history up to the selected month.
  const params = (g === "quarter" || g === "year") && start ? { ...t, period: "custom", start, end: endOfMonth(t.value) } : t;
  const { data, loading, error } = useApi<any>("/finance/revenue-expenditure", { ...params, granularity: g });
  const traces = useMemo(() => data ? [
    { type: "bar", name: "Bank revenue", x: data.x, y: data.series.bank_revenue, marker: { color: SERIES.revenue }, hovertemplate: `%{y:,.0f} ${cur}` },
    { type: "bar", name: "Bank operating expenditure", x: data.x, y: data.series.bank_opex, marker: { color: SERIES.opex }, hovertemplate: `%{y:,.0f} ${cur}` },
    { type: "scatter", mode: "lines+markers", name: "Operating profit", x: data.x, y: data.series.operating_profit, line: { color: SERIES.profit, width: 3 }, hovertemplate: `%{y:,.0f} ${cur}` },
    { type: "scatter", mode: "lines", name: "Sherin AI expenditure (cash, in opex)", x: data.x, y: data.series.ai_opex_cash, yaxis: "y2", line: { color: SERIES.ai, width: 2.5, dash: "dot" }, hovertemplate: `%{y:,.0f} ${cur}` },
  ] : [], [data, cur]);
  return (
    <ChartCard id="graph-a" title="Revenue vs Expenditure" subtitle={`Bank revenue, operating expenditure, operating profit and Sherin AI expenditure · ${data?.period?.start ?? ""} → ${data?.period?.end ?? ""}`}
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="actual" /></>}
      actions={<Segmented label="Granularity" value={g} onChange={setG} options={["day", "week", "month", "quarter", "year"].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} />}>
      <ErrorBox error={error} />
      {loading && !data ? <Spinner /> : <Plot ariaLabel="Revenue vs expenditure chart" testId="graph-a-plot" height={H + 40} data={traces}
        layout={{ barmode: "group", yaxis: { title: { text: cur }, tickformat: "~s" }, yaxis2: { title: { text: `AI (${cur})` }, overlaying: "y", side: "right", tickformat: "~s", showgrid: false }, margin: { l: 64, r: 64, t: 12, b: 48 } }} />}
      {data && <Note>{data.notes.join(" ")}</Note>}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph B
export function GraphB() {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/contribution", p);
  const ttm = useApi<any>("/finance/contribution", { ...p, period: "ttm" });
  const [view, setView] = useState("waterfall");
  return (
    <ChartCard id="graph-b" title="Sherin AI Financial Contribution" subtitle="How net economic benefit is built. Cost avoidance is never treated as revenue."
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="estimated" /><Badge tone="green">Net {money(data.summary.net_benefit, cur)}</Badge><Badge tone="dark">ROI {data.summary.roi_pct ?? "—"}%</Badge></>}
      actions={<Segmented label="View" value={view} onChange={setView} options={[{ value: "waterfall", label: "Waterfall" }, { value: "monthly", label: "12-month trend" }]} />}>
      {loading && !data ? <Spinner /> : view === "waterfall" && data ? (
        <Plot ariaLabel="Net benefit waterfall" testId="graph-b-plot" height={H}
          data={[{ type: "waterfall", orientation: "v", x: data.waterfall.map((w: any) => wrap(w.label, 16)), y: data.waterfall.map((w: any) => w.value), measure: data.waterfall.map((w: any) => w.measure),
            text: data.waterfall.map((w: any) => money(w.value, cur)), textposition: "outside", connector: { line: { color: "#C9D9D1" } },
            increasing: { marker: { color: SERIES.savings } }, decreasing: { marker: { color: SERIES.cost } }, totals: { marker: { color: SERIES.profit } },
            hovertemplate: `%{x}<br>%{y:,.2f} ${cur}<extra></extra>` }]}
          layout={{ showlegend: false, xaxis: { tickangle: 0, automargin: true, tickfont: { size: 11 } }, yaxis: { tickformat: "~s", title: { text: cur } }, hovermode: "closest", margin: { l: 64, r: 16, t: 24, b: 90 } }} />
      ) : ttm.data ? (
        <Plot ariaLabel="Monthly AI contribution" testId="graph-b-monthly" height={H}
          data={[
            { type: "bar", name: "AI-attributed revenue (inside fee income)", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => m.attributed_revenue), marker: { color: "#7FC8A9" } },
            { type: "bar", name: "Estimated labour cost avoidance", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => m.cost_avoidance), marker: { color: SERIES.savings } },
            { type: "bar", name: "Realized savings (subset)", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => m.realized_savings), marker: { color: SERIES.profit } },
            { type: "bar", name: "AI operating expenditure", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => -m.ai_opex), marker: { color: SERIES.ai } },
            { type: "bar", name: "Implementation (allocated)", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => -m.implementation), marker: { color: SERIES.cost } },
            { type: "scatter", mode: "lines+markers", name: "Net economic benefit", x: ttm.data.monthly.map((m: any) => m.month), y: ttm.data.monthly.map((m: any) => m.net_benefit), line: { color: "#062A1F", width: 3 } },
          ]} layout={{ barmode: "relative", yaxis: { tickformat: "~s", title: { text: cur } } }} />
      ) : <Spinner />}
      {data && <Note>{data.notes.join(" ")}</Note>}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph C
export function GraphC() {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/human-vs-ai", p);
  const comps = [["model", "Model", "#0B3D2E"], ["compute", "Compute", "#13795B"], ["infrastructure", "Infrastructure", "#2BB673"], ["tooling", "Tooling", "#7FC8A9"],
    ["human_review", "Human review", SERIES.ai], ["rework", "Rework", SERIES.cost]] as const;
  return (
    <ChartCard id="graph-c" title="Human vs AI Cost" subtitle="Cost per verified task. AI-assisted cost includes human review, rework and failed attempts."
      badges={data && <><DataClassBadge dc={data.data_class} /><Badge tone="amber">Baselines: configured assumptions</Badge></>}>
      {loading && !data ? <Spinner /> : data && (
        <Plot ariaLabel="Human vs AI cost per task" testId="graph-c-plot" height={H}
          data={[
            { type: "bar", name: "Human-only baseline", x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => r.human_only_per_task), offsetgroup: "h", marker: { color: SERIES.opex },
              hovertemplate: `%{x}<br>Human-only: %{y:,.2f} ${cur}<extra></extra>` },
            ...comps.map(([k, name, color]) => ({ type: "bar", name: `AI: ${name}`, x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => r.ai_per_task[k]), offsetgroup: "a",
              marker: { color }, hovertemplate: `%{x}<br>${name}: %{y:,.2f} ${cur}<extra></extra>` })),
          ]} layout={{ barmode: "stack", yaxis: { title: { text: `${cur} per verified task` } }, xaxis: { tickangle: 0 }, hovermode: "closest", bargroupgap: 0.1, margin: { t: 64, b: 56 } }} />
      )}
      {data && <Table dense columns={[{ key: "label", label: "Workflow" }, { key: "verified_tasks", label: "Verified", align: "right" },
        { key: "h", label: "Human / task", align: "right", render: (r) => money(r.human_only_per_task, cur) }, { key: "a", label: "AI-assisted / task", align: "right", render: (r) => money(r.ai_assisted_per_task, cur) },
        { key: "b", label: "Baseline", render: (r) => `${r.baseline_hours} h × ${money(r.baseline_rate, cur)}` }]} rows={data.rows} />}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph D
export function GraphD() {
  const { p, t, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/ai-costs", p);
  const trend = useApi<any>("/finance/ai-costs", t);
  const [cat, setCat] = useState<string | null>(null);
  const cats = data?.categories ?? [];
  return (
    <ChartCard id="graph-d" title="Sherin AI Cost Breakdown" subtitle="Click any category to inspect the underlying cost records."
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="actual" /><Badge tone="dark">Total {money(data.total, cur)}</Badge></>}>
      {loading && !data ? <Spinner /> : (
        <div className="grid gap-4 xl:grid-cols-5">
          <div className="xl:col-span-2">
            <Plot ariaLabel="AI cost breakdown donut" testId="graph-d-plot" height={H - 20} onClick={(ev) => setCat(cats[ev.points?.[0]?.pointNumber]?.category ?? null)}
              data={[{ type: "pie", hole: 0.58, labels: cats.map((c: any) => c.label), values: cats.map((c: any) => c.value), sort: false,
                marker: { colors: cats.map((c: any) => CAT_COLOR[c.category]) }, textinfo: "percent", textposition: "inside", insidetextorientation: "horizontal", hovertemplate: `%{label}<br>%{value:,.2f} ${cur} (%{percent})<extra></extra>` }]}
              layout={{ showlegend: false, margin: { l: 8, r: 8, t: 8, b: 8 }, annotations: [{ text: `<b>${money(data?.total, cur)}</b><br>total`, showarrow: false, font: { size: 16, family: "Fraunces" } }] }} />
          </div>
          <div className="xl:col-span-3">
            {trend.data && <Plot ariaLabel="Monthly AI cost by category" height={H - 20} onClick={(ev) => setCat(Object.keys(trend.data.monthly.series)[ev.points?.[0]?.curveNumber] ?? null)}
              data={Object.entries(trend.data.monthly.series).map(([k, ys]) => ({ type: "bar", name: cats.find((c: any) => c.category === k)?.label ?? k, x: trend.data.monthly.x, y: ys, marker: { color: CAT_COLOR[k] } }))}
              layout={{ barmode: "stack", yaxis: { tickformat: "~s", title: { text: cur } }, margin: { t: 70 } }} />}
          </div>
          <div className="flex flex-wrap gap-1.5 xl:col-span-5">
            {cats.map((c: any) => <button key={c.category} type="button" onClick={() => setCat(c.category)} className="inline-flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs hover:border-flo-600 hover:bg-flo-50">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: CAT_COLOR[c.category] }} aria-hidden />{c.label}: <strong className="tnum">{money(c.value, cur)}</strong> <span className="text-muted">({c.share_pct}%)</span></button>)}
          </div>
        </div>
      )}
      <CostRecordsDrawer category={cat} onClose={() => setCat(null)} />
    </ChartCard>
  );
}

export function CostRecordsDrawer({ category, onClose }: { category: string | null; onClose: () => void }) {
  const { p, cur } = useParams();
  const [page, setPage] = useState(0);
  const { data, loading } = useApi<any>(category ? `/finance/ai-costs/${category}/records` : null, { ...p, limit: 50, offset: page * 50 });
  return (
    <Drawer open={!!category} onClose={() => { setPage(0); onClose(); }} title={data ? `${data.label} — cost records` : "Cost records"} width={860}>
      {loading || !data ? <Spinner /> : (
        <>
          <p className="mb-2 text-sm text-muted">{num(data.count)} records in {p.period} {p.value}, largest first. <DataClassBadge dc={data.data_class} /></p>
          <Table dense columns={[{ key: "date", label: "Date" }, { key: "description", label: "Description" }, { key: "agent", label: "Agent" }, { key: "vendor", label: "Vendor" },
            { key: "basis", label: "Basis" }, { key: "amount", label: `Amount (${cur})`, align: "right", render: (r) => money(r.amount, cur, false) }]} rows={data.records} />
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" className="text-sm text-flo-800 disabled:opacity-40" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</button>
            <button type="button" className="text-sm text-flo-800 disabled:opacity-40" disabled={(page + 1) * 50 >= data.count} onClick={() => setPage(page + 1)}>Next</button>
          </div>
        </>
      )}
    </Drawer>
  );
}

// ------------------------------------------------------------------------------------------- Graph E
export function GraphE({ full = false }: { full?: boolean }) {
  const { t, p, cur } = useParams();
  const [g, setG] = useState("week");
  const { data, loading } = useApi<any>("/finance/tokens", { ...t, granularity: g });
  const month = useApi<any>("/finance/tokens", { ...p, granularity: "month" });
  const [mode, setMode] = useState("provider");
  const tot = month.data?.totals;
  return (
    <ChartCard id="graph-e" title="Token Consumption" subtitle="Local Qwen inference is shown with its allocated compute and electricity cost, even with zero API charges."
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="actual" /></>}
      actions={<><Segmented label="Token series" value={mode} onChange={setMode} options={[{ value: "provider", label: "Local vs paid" }, { value: "io", label: "Input / output / cached" }]} />
        <Segmented label="Granularity" value={g} onChange={setG} options={[{ value: "day", label: "Day" }, { value: "week", label: "Week" }, { value: "month", label: "Month" }]} /></>}>
      {tot && (
        <div className="mb-2 grid grid-cols-2 gap-2 md:grid-cols-6">
          {[["Total tokens", compact(tot.tokens)], ["Per task", compact(tot.tokens_per_task)], ["Per successful task", compact(tot.tokens_per_successful_task)],
            ["Cost / million", money(tot.cost_per_million, cur)], ["Token cost", money(tot.cost, cur)], ["Verified tasks / M tokens", num(tot.verified_tasks_per_million_tokens, 2)]].map(([l, v]) => (
            <div key={l} className="rounded-xl bg-flo-50 p-2.5"><div className="text-[10px] font-semibold uppercase tracking-wide text-muted">{l}</div><div className="font-display text-lg font-semibold text-flo-900 tnum">{v}</div></div>))}
        </div>
      )}
      {loading && !data ? <Spinner /> : data && (
        <Plot ariaLabel="Token consumption over time" testId="graph-e-plot" height={full ? H + 40 : H}
          data={[
            ...(mode === "provider"
              ? [{ type: "bar", name: "Local Qwen tokens", x: data.x, y: data.series.local_qwen, marker: { color: SERIES.local } }, { type: "bar", name: "Paid model tokens", x: data.x, y: data.series.paid_api, marker: { color: SERIES.paid } }]
              : [{ type: "bar", name: "Input", x: data.x, y: data.series.input, marker: { color: SERIES.local } }, { type: "bar", name: "Output", x: data.x, y: data.series.output, marker: { color: SERIES.paid } },
                { type: "scatter", mode: "lines", name: "Cached (subset of input)", x: data.x, y: data.series.cached, line: { color: SERIES.cached, dash: "dot" } }]),
            { type: "scatter", mode: "lines+markers", name: `Token cost (${cur})`, x: data.x, y: data.series.cost, yaxis: "y2", line: { color: SERIES.cost, width: 2.5 } },
          ]} layout={{ barmode: "stack", yaxis: { title: { text: "tokens" }, tickformat: "~s" }, yaxis2: { overlaying: "y", side: "right", title: { text: cur }, showgrid: false }, margin: { l: 64, r: 64, t: 12, b: 48 } }} />
      )}
      {month.data && (
        <div className="mt-3 grid gap-4 lg:grid-cols-2">
          <Plot ariaLabel="Tokens per agent" height={360} data={[{ type: "bar", orientation: "h", y: month.data.per_agent.map((a: any) => shortAgent(a.label)), x: month.data.per_agent.map((a: any) => a.tokens),
            marker: { color: AGENT_COLORS }, customdata: month.data.per_agent.map((a: any) => [a.tokens_per_task, a.cost]),
            hovertemplate: `%{y}<br>%{x:,} tokens<br>%{customdata[0]:,} per task<br>%{customdata[1]:,.2f} ${cur}<extra></extra>` }]}
            layout={{ showlegend: false, margin: { l: 150, r: 16, t: 8, b: 32 }, yaxis: { autorange: "reversed" }, hovermode: "closest", xaxis: { tickformat: "~s" } }} />
          <Table dense columns={[{ key: "p", label: "Provider", render: (r) => r.p === "local_qwen" ? "Local Qwen (Ollama)" : "Paid model" }, { key: "total", label: "Tokens", align: "right", render: (r) => compact(r.total) },
            { key: "cost", label: "Cost", align: "right", render: (r) => money(r.cost, cur) }, { key: "cpm", label: "Cost / M", align: "right", render: (r) => money(r.cost_per_million, cur) }]}
            rows={Object.entries(month.data.providers).map(([k, v]: any) => ({ p: k, ...v }))} />
        </div>
      )}
      {month.data && <Note>{month.data.notes.join(" ")} Local cost components this period: compute {money(month.data.local_cost_components.allocated_compute, cur)}, electricity {money(month.data.local_cost_components.electricity, cur)}.</Note>}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph F
export function GraphF() {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/forecast", p);
  const [metric, setMetric] = useState("net_benefit");
  const colors: Record<string, string> = { best: SERIES.savings, base: SERIES.profit, downside: SERIES.cost };
  return (
    <ChartCard id="graph-f" title="Revenue and Cost Forecast" subtitle="Scenario projections from trailing trends. Not guarantees."
      badges={<><Badge tone="amber">Forecast</Badge>{data && <DataClassBadge dc={data.data_class} />}</>}
      actions={<Segmented label="Forecast metric" value={metric} onChange={setMetric} options={[{ value: "net_benefit", label: "Net benefit" }, { value: "cumulative_vs_capex", label: "Break-even" },
        { value: "revenue", label: "Revenue" }, { value: "ai_opex", label: "AI opex" }, { value: "estimated_savings", label: "Savings" }]} />}>
      {loading && !data ? <Spinner /> : data?.available ? (
        <>
          <Plot ariaLabel="Forecast scenarios" testId="graph-f-plot" height={H}
            data={[
              ...(metric === "revenue" || metric === "net_benefit" ? [{ type: "scatter", mode: "lines", name: "History", x: data.history.map((h: any) => h.month), y: data.history.map((h: any) => h[metric === "revenue" ? "revenue" : "net_benefit"]), line: { color: "#5B6B65", width: 3 } }] : []),
              ...Object.entries(data.scenarios).map(([k, s]: any) => ({ type: "scatter", mode: "lines+markers", name: s.label, x: s.series.map((x: any) => x.month), y: s.series.map((x: any) => x[metric]), line: { color: colors[k], width: 2.5, dash: k === "base" ? "solid" : "dash" } })),
            ]}
            layout={{ yaxis: { tickformat: "~s", title: { text: cur } }, shapes: metric === "cumulative_vs_capex" ? [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: 0, y1: 0, line: { color: "#B4413C", dash: "dot" } }] : [] }} />
          <div className="mt-2 grid gap-2 md:grid-cols-3">
            {Object.entries(data.scenarios).map(([k, s]: any) => (
              <div key={k} className="rounded-xl border border-line p-3 text-sm"><div className="font-semibold" style={{ color: colors[k] }}>{s.label}</div>
                <div className="text-muted">Break-even vs implementation capex: <strong className="text-flo-900">{s.breakeven_month ?? "not within horizon"}</strong>{s.breakeven_basis === "historical" && <span className="text-xs"> (historical)</span>}</div>
                <div className="text-xs text-muted">Usage growth ×{s.assumptions.usage_growth}, cost/task ×{s.assumptions.cost_per_task}, revenue trend ×{s.assumptions.revenue_trend}</div></div>))}
          </div>
          <Note>{data.disclaimer} Assumptions: task growth {data.assumptions.task_growth_per_month_pct}%/month, verification {data.assumptions.verification_rate_pct}%, variable AI cost {money(data.assumptions.variable_ai_cost_per_task, cur)}/task, platform overhead {money(data.assumptions.monthly_platform_overhead, cur)}/month, implementation capex {money(data.assumptions.implementation_capex, cur)}.</Note>
        </>
      ) : <Note>{data?.reason ?? "Forecast unavailable."}</Note>}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph G
export function GraphG() {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/agents", p);
  return (
    <ChartCard id="graph-g" title="Agent Productivity Economics" subtitle="Completed work, human hours avoided vs still required, and net estimated savings per agent."
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="estimated" /></>}>
      {loading && !data ? <Spinner /> : data && (
        <>
          <Plot ariaLabel="Agent productivity" testId="graph-g-plot" height={H}
            data={[
              { type: "bar", name: "Human hours avoided", x: data.rows.map((r: any) => shortAgent(r.label)), y: data.rows.map((r: any) => r.human_hours_avoided), marker: { color: SERIES.savings } },
              { type: "bar", name: "Human hours still required", x: data.rows.map((r: any) => shortAgent(r.label)), y: data.rows.map((r: any) => r.human_hours_required), marker: { color: SERIES.opex } },
              { type: "bar", name: "AI execution hours", x: data.rows.map((r: any) => shortAgent(r.label)), y: data.rows.map((r: any) => r.ai_execution_hours), marker: { color: SERIES.ai } },
              { type: "scatter", mode: "markers", name: `Net estimated savings (${cur})`, x: data.rows.map((r: any) => shortAgent(r.label)), y: data.rows.map((r: any) => r.net_estimated_savings), yaxis: "y2",
                marker: { size: 13, color: SERIES.profit, symbol: "diamond" } },
            ]} layout={{ barmode: "group", yaxis: { title: { text: "hours" } }, yaxis2: { overlaying: "y", side: "right", title: { text: cur }, tickformat: "~s", showgrid: false }, xaxis: { tickangle: -35 }, margin: { l: 56, r: 64, t: 40, b: 90 } }} />
          <Table dense columns={[{ key: "label", label: "Agent" }, { key: "completed", label: "Completed", align: "right" }, { key: "cost", label: "Cost / successful task", align: "right", render: (r) => money(r.cost_per_successful_task, cur) },
            { key: "q", label: "Quality pass", align: "right", render: (r) => `${r.quality_pass_rate}%` }, { key: "tokens", label: "Tokens", align: "right", render: (r) => compact(r.tokens) },
            { key: "n", label: "Net savings", align: "right", render: (r) => <span className={r.net_estimated_savings < 0 ? "text-red" : "text-flo-800"}>{money(r.net_estimated_savings, cur)}</span> }]} rows={data.rows} />
          <Note>{data.notes[0]} {data.verification_agent.note}</Note>
        </>
      )}
    </ChartCard>
  );
}

// ------------------------------------------------------------------------------------------- Graph H
export function GraphH() {
  const { p, cur } = useParams();
  const { data, loading } = useApi<any>("/finance/departments", p);
  return (
    <ChartCard id="graph-h" title="Financial Value by Department" subtitle="Verified productivity gains and financial impact (cost avoidance + attributed incremental profit − unrecovered cost)."
      badges={data && <><DataClassBadge dc={data.data_class} /><BasisBadge basis="estimated" /></>}>
      {loading && !data ? <Spinner /> : data && (
        <Plot ariaLabel="Department value" testId="graph-h-plot" height={H}
          data={[
            { type: "bar", name: `Cost avoidance (${cur})`, x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => r.cost_avoidance), marker: { color: SERIES.savings } },
            { type: "bar", name: `Attributed incremental profit (${cur})`, x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => r.incremental_profit), marker: { color: "#7FC8A9" } },
            { type: "bar", name: `Unrecovered AI cost (${cur})`, x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => -r.unrecovered_cost), marker: { color: SERIES.cost } },
            { type: "scatter", mode: "lines+markers+text", name: "Productivity gain %", x: data.rows.map((r: any) => wrap(r.label, 12)), y: data.rows.map((r: any) => r.productivity_gain_pct), yaxis: "y2",
              text: data.rows.map((r: any) => `${r.productivity_gain_pct}%`), textposition: "top center", line: { color: SERIES.ai, width: 2 } },
          ]} layout={{ barmode: "relative", yaxis: { tickformat: "~s", title: { text: cur } }, yaxis2: { overlaying: "y", side: "right", title: { text: "%" }, range: [0, 110], showgrid: false }, xaxis: { tickangle: 0 }, margin: { l: 64, r: 56, t: 64, b: 56 } }} />
      )}
      {data && <Note>{data.notes[0]}</Note>}
    </ChartCard>
  );
}
