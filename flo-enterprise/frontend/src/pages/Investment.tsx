import { useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useMemo, useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { DataTable } from "@/components/DataTable";
import { GeoMap } from "@/components/GeoMap";
import { Badge, Button, ErrorState, PageHeader, Select, Spinner, Stat, Tabs } from "@/components/ui";
import { api, download } from "@/lib/api";
import { useApp } from "@/lib/app";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { cad, compact, month, num, pct } from "@/lib/format";

type Tab = "explorer" | "funds" | "performance" | "risk" | "market" | "geo";

export default function Investment() {
  const { can } = useApp();
  const [tab, setTab] = useState<Tab>(can("investment:read") ? "explorer" : "risk");
  const tabs: { id: Tab; label: string }[] = [
    ...(can("investment:read") ? [{ id: "explorer" as Tab, label: "Portfolio Explorer" }] : []),
    { id: "funds", label: "Fund Research" }, { id: "performance", label: "Performance & Benchmarks" },
    { id: "risk", label: "Risk Intelligence" }, { id: "market", label: "Market Intelligence" }, { id: "geo", label: "Sector & Geographic Exposure" },
  ];
  return (
    <div className="space-y-4">
      <PageHeader title="Investment Intelligence" subtitle="Deterministic analytics over synthetic portfolio, fund accounting and market data" />
      <Tabs tabs={tabs} value={tab} onChange={setTab} />
      {tab === "explorer" && <Explorer />}
      {tab === "funds" && <Funds />}
      {tab === "performance" && <Performance />}
      {tab === "risk" && <Risk />}
      {tab === "market" && <Market />}
      {tab === "geo" && <Geo />}
    </div>
  );
}

const ch = createColumnHelper<any>();

function Explorer() {
  const [mandate, setMandate] = useState("");
  const [sel, setSel] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["portfolios", mandate], queryFn: () => api(`/api/investment/portfolios${mandate ? `?mandate=${encodeURIComponent(mandate)}` : ""}`) });
  const cols = [
    ch.accessor("id", { header: "Portfolio" }), ch.accessor("mandate", { header: "Mandate" }), ch.accessor("risk_profile", { header: "Profile" }),
    ch.accessor("market_value", { header: "Market value", cell: (c) => cad(c.getValue()) }),
    ch.accessor("twr_annualized", { header: "TWR p.a.", cell: (c) => pct(c.getValue()) }),
    ch.accessor("excess_annualized", { header: "Excess p.a.", cell: (c) => <span className={c.getValue() >= 0 ? "text-pos" : "text-crit"}>{pct(c.getValue())}</span> }),
    ch.accessor("volatility", { header: "Vol", cell: (c) => pct(c.getValue()) }), ch.accessor("sharpe", { header: "Sharpe", cell: (c) => num(c.getValue()) }),
    ch.accessor("max_drawdown", { header: "Max DD", cell: (c) => pct(c.getValue()) }),
    ch.accessor("top_weight", { header: "Top holding", cell: (c) => <span className={c.row.original.concentration_breach ? "text-warn" : ""}>{pct(c.getValue(), 1)}</span> }),
    ch.accessor("drift", { header: "Drift", cell: (c) => pct(c.getValue(), 1) }),
  ];
  if (sel) return <div className="space-y-3"><Button size="sm" onClick={() => setSel(null)}>← Back to explorer</Button><PortfolioDetail id={sel} /></div>;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Select aria-label="Mandate filter" value={mandate} onChange={(e) => setMandate(e.target.value)}>
          <option value="">All mandates</option>{["Conservative Income", "Balanced Growth", "Canadian Dividend", "Global Equity", "Concentrated Growth"].map((m) => <option key={m}>{m}</option>)}
        </Select>
        <Button size="sm" onClick={() => download("/api/exports/portfolios.csv", "flo-portfolios.csv")}>Export CSV</Button>
        <span className="text-xs text-muted">Client identity is withheld in investment oversight views (data minimization).</span>
      </div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : <DataTable label="Portfolios" data={q.data.data.portfolios} columns={cols} onRowClick={(r: any) => setSel(r.id)} />}
    </div>
  );
}

export function PortfolioDetail({ id }: { id: string }) {
  const q = useQuery({ queryKey: ["portfolio", id], queryFn: () => api(`/api/investment/portfolios/${id}`) });
  const geo = useQuery({ queryKey: ["pgeo", id], queryFn: () => api(`/api/investment/geographic?scope=portfolio&portfolio_id=${id}`) });
  const tk = tokens();
  const d = q.data?.data;
  const opts = useMemo(() => {
    if (!d) return null;
    const x = axis({ type: "category", data: d.months.map(month) });
    const yPct = axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } });
    const tip = { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v) };
    const alloc = Object.entries(d.allocation.asset_class);
    const sectors = Object.entries(d.allocation.sector);
    const contrib = Object.entries(d.contribution_12m.by_sector) as [string, number][];
    let run = 0;
    const wfBase: number[] = [], wfVal: any[] = [];
    contrib.forEach(([, v]) => { wfBase.push(v >= 0 ? run : run + v); wfVal.push({ value: Math.abs(v), itemStyle: { color: v >= 0 ? tk.series[2] : tk.series[1], borderRadius: 3 } }); run += v; });
    return {
      perf: { ...baseOption(), tooltip: tip, xAxis: x, yAxis: yPct, series: [
        { name: "Portfolio (TWR, cumulative)", type: "line", data: d.cumulative, symbol: "none", lineStyle: { width: 2 } },
        { name: "Benchmark", type: "line", data: d.benchmark_cumulative, symbol: "none", lineStyle: { width: 2, type: "dashed" } }] },
      rel: { ...baseOption(), tooltip: tip, xAxis: x, yAxis: yPct, series: [{ name: "Relative return", type: "bar", data: d.relative.map((v: number) => ({ value: v, itemStyle: { color: v >= 0 ? tk.series[2] : tk.series[1], borderRadius: 3 } })) }] },
      dd: { ...baseOption(), tooltip: tip, xAxis: x, yAxis: yPct, series: [{ name: "Drawdown", type: "line", areaStyle: { opacity: 0.35 }, data: d.drawdown, symbol: "none", lineStyle: { width: 2, color: tk.series[1] }, itemStyle: { color: tk.series[1] } }] },
      donut: { ...baseOption(), tooltip: { ...baseOption().tooltip, valueFormatter: (v: number) => pct(v) }, legend: { ...baseOption().legend, bottom: 0, top: "auto" },
        series: [{ type: "pie", radius: ["50%", "75%"], itemStyle: { borderColor: tk.surface, borderWidth: 2, borderRadius: 4 }, label: { color: tk.ink, formatter: "{b}\n{d}%" }, data: alloc.map(([k, v]) => ({ name: k, value: v })) }] },
      tree: { ...baseOption(), tooltip: { ...baseOption().tooltip, valueFormatter: (v: number) => pct(v) },
        series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, itemStyle: { borderColor: tk.surface, gapWidth: 2 },
          visualMin: 0, visualMax: Math.max(...sectors.map(([, v]) => v as number)), colorMappingBy: "value", levels: [{ color: tk.seq.slice(1) }],
          label: { color: "#fff", formatter: (p: any) => `${p.name}\n${pct(p.value, 1)}` }, data: sectors.map(([k, v]) => ({ name: k, value: v })) }] },
      wf: { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", formatter: (p: any) => `${p[1].name}: ${pct(contrib[p[1].dataIndex][1], 2)}` },
        grid: { left: 40, right: 10, top: 20, bottom: 70, containLabel: true },
        xAxis: axis({ type: "category", data: contrib.map(([k]) => k), axisLabel: { rotate: 35, color: tk.muted, fontSize: 10 } }), yAxis: yPct,
        series: [{ type: "bar", stack: "c", itemStyle: { color: "transparent" }, data: wfBase, silent: true }, { type: "bar", stack: "c", data: wfVal }] },
    };
  }, [d, tk]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const mtr = d.metrics;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2"><h2 className="text-lg font-semibold">{d.portfolio.name}</h2><Badge tone="blue">{mtr.mandate}</Badge>
        <Badge>benchmark {mtr.benchmark_id}</Badge>{d.concentration.breaches.length > 0 && <Badge tone="warn">{d.concentration.breaches.length} single-issuer breach(es)</Badge>}</div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-8">
        <Stat label="Market value" value={cad(mtr.market_value)} /><Stat label="TWR p.a. (24m)" value={pct(mtr.twr_annualized)} />
        <Stat label="MWR p.a." value={pct(d.mwr_annualized)} /><Stat label="Benchmark p.a." value={pct(mtr.twr_annualized - mtr.excess_annualized)} />
        <Stat label="Volatility" value={pct(mtr.volatility)} /><Stat label="Sharpe" value={num(mtr.sharpe)} />
        <Stat label="Max drawdown" value={pct(mtr.max_drawdown)} /><Stat label="Effective N (1/HHI)" value={num(mtr.effective_n, 1)} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard id="performance" title="Performance vs benchmark (cumulative)" lineage={q.data.lineage} option={opts?.perf} askContext={{ portfolio_id: id }}
          rows={d.months.map((m: string, i: number) => ({ month: m, portfolio_return: d.returns[i], benchmark_return: d.benchmark_returns[i], market_value: d.market_values[i], external_flow: d.flows[i] }))} />
        <ChartCard id="relative_return" title="Relative return (geometric, cumulative)" option={opts?.rel} askContext={{ portfolio_id: id }} />
        <ChartCard id="performance" title="Drawdown" option={opts?.dd} askContext={{ portfolio_id: id }} />
        <ChartCard id="concentration" title="Asset allocation" option={opts?.donut} askContext={{ portfolio_id: id }} rows={Object.entries(d.allocation.asset_class).map(([k, v]) => ({ asset_class: k, weight: v as number }))} />
        <ChartCard id="concentration" title="Sector exposure" option={opts?.tree} askContext={{ portfolio_id: id }} rows={Object.entries(d.allocation.sector).map(([k, v]) => ({ sector: k, weight: v as number }))} />
        <ChartCard id="performance" title="Contribution by sector (last 12 months)" subtitle={`${d.contribution_12m.method} Portfolio Σ ${pct(d.contribution_12m.portfolio_sum)} vs benchmark Σ ${pct(d.contribution_12m.benchmark_sum)}`}
          option={opts?.wf} askContext={{ portfolio_id: id }} rows={Object.entries(d.contribution_12m.by_sector).map(([k, v]) => ({ sector: k, contribution: v as number }))} />
        <ChartCard id="geographic_exposure" title="Geographic exposure" lineage={geo.data?.lineage} rows={geo.data?.data.countries} loading={geo.isLoading}>
          {geo.data && <GeoMap rows={geo.data.data.countries} height={260} />}
        </ChartCard>
        <ChartCard id="concentration" title="Holdings (current vs target weight)" rows={d.holdings}>
          <DataTable label="Holdings" search={false} pageSize={15} data={d.holdings} columns={[ch.accessor("name", { header: "Security" }), ch.accessor("sector", { header: "Sector" }),
            ch.accessor("current_weight", { header: "Weight", cell: (c) => <span className={c.getValue() > d.concentration.limit ? "text-warn font-medium" : ""}>{pct(c.getValue())}</span> }),
            ch.accessor("drift", { header: "Drift", cell: (c) => pct(c.getValue()) }), ch.accessor("market_value", { header: "Value", cell: (c) => cad(c.getValue()) })]} />
        </ChartCard>
      </div>
    </div>
  );
}

function Funds() {
  const [sel, setSel] = useState<string | null>(null);
  const q = useQuery({ queryKey: ["funds"], queryFn: () => api("/api/investment/funds") });
  const det = useQuery({ queryKey: ["fund", sel], queryFn: () => api(`/api/investment/funds/${sel}`), enabled: !!sel });
  const tk = tokens();
  const f = det.data?.data;
  const opts = useMemo(() => f && ({
    perf: { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v) }, xAxis: axis({ type: "category", data: f.months.map(month) }),
      yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      series: [{ name: "Fund (gross)", type: "line", data: f.cumulative, symbol: "none", lineStyle: { width: 2 } }, { name: "Benchmark", type: "line", data: f.benchmark_cumulative, symbol: "none", lineStyle: { width: 2, type: "dashed" } }] },
    aum: { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `CAD ${compact(v)}` }, xAxis: axis({ type: "category", data: f.months.map(month) }),
      yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }), series: [{ name: "Net flows", type: "bar", data: f.net_flows.map((v: number) => ({ value: v, itemStyle: { color: v >= 0 ? tk.series[2] : tk.series[1], borderRadius: 3 } })) }] },
    sect: { ...baseOption(), tooltip: { ...baseOption().tooltip, valueFormatter: (v: number) => pct(v) }, legend: { show: false },
      series: [{ type: "pie", radius: ["50%", "75%"], itemStyle: { borderColor: tk.surface, borderWidth: 2 }, label: { color: tk.ink, formatter: "{b} {d}%", fontSize: 10 },
        data: Object.entries(f.sector_weights).slice(0, 7).map(([k, v]) => ({ name: k, value: v })).concat(Object.keys(f.sector_weights).length > 7 ? [{ name: "Other", value: Object.values(f.sector_weights).slice(7).reduce((a: number, b: any) => a + b, 0) as number }] : []) }] },
  }), [f, tk]);
  const cols = [ch.accessor("name", { header: "Fund" }), ch.accessor("vehicle", { header: "Vehicle" }), ch.accessor("asset_class", { header: "Asset class" }),
    ch.accessor("fee_bps", { header: "Fee (bps)" }), ch.accessor("aum", { header: "AUM", cell: (c) => `CAD ${compact(c.getValue())}` }),
    ch.accessor("return_12m", { header: "12m", cell: (c) => pct(c.getValue()) }), ch.accessor("benchmark_12m", { header: "Bench 12m", cell: (c) => pct(c.getValue()) }),
    ch.accessor("sharpe", { header: "Sharpe", cell: (c) => num(c.getValue()) }), ch.accessor("net_flows_12m", { header: "Net flows 12m", cell: (c) => `CAD ${compact(c.getValue())}` })];
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="space-y-4">
      {sel && f && (
        <div className="space-y-3">
          <div className="flex items-center gap-2"><Button size="sm" onClick={() => setSel(null)}>← All funds</Button><h2 className="font-semibold">{f.product.name}</h2>
            <Badge>{f.product.vehicle}</Badge><Badge tone="blue">{f.product.strategy}</Badge><Badge>{f.fee_bps[f.fee_bps.length - 1]} bps</Badge></div>
          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard id="relative_return" title="Cumulative return vs benchmark" option={opts?.perf} lineage={det.data.lineage} />
            <ChartCard id="net_flows" title="Monthly net flows" option={opts?.aum} />
            <ChartCard id="concentration" title="Sector weights" option={opts?.sect} rows={f.top_holdings} />
          </div>
          <p className="text-xs text-muted">Fee impact (CAD 100,000, 6% gross, 10 years): ending value {cad(f.fee_impact_100k_10y.ending_with_fee)} vs {cad(f.fee_impact_100k_10y.ending_no_fee)} without fees (drag {cad(f.fee_impact_100k_10y.fee_drag)}). General information, not advice.</p>
        </div>
      )}
      <DataTable label="Funds" data={q.data.data.funds} columns={cols} onRowClick={(r: any) => setSel(r.id)} />
    </div>
  );
}

function Performance() {
  const q = useQuery({ queryKey: ["funds"], queryFn: () => api("/api/investment/funds") });
  const tk = tokens();
  const opt = useMemo(() => {
    if (!q.data) return null;
    const rows = [...q.data.data.funds].map((f: any) => ({ ...f, rel: f.return_12m - f.benchmark_12m })).sort((a, b) => a.rel - b.rel);
    return { ...baseOption(), grid: { left: 10, right: 10, top: 10, bottom: 10, containLabel: true },
      tooltip: { ...baseOption().tooltip, trigger: "axis", formatter: (p: any) => { const r = rows[p[0].dataIndex]; return `${r.name}<br/>Fund ${pct(r.return_12m)} · Bench ${pct(r.benchmark_12m)}<br/>Relative ${pct(r.rel)}`; } },
      xAxis: axis({ type: "category", data: rows.map((r: any) => r.id), axisLabel: { show: false } }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      series: [{ type: "bar", data: rows.map((r: any) => ({ value: r.rel, itemStyle: { color: r.rel >= 0 ? tk.series[2] : tk.series[1], borderRadius: 2 } })) }] };
  }, [q.data, tk]);
  const sc = useQuery({ queryKey: ["rr", "funds"], queryFn: () => api("/api/investment/risk-return?universe=funds") });
  const scOpt = useMemo(() => {
    if (!sc.data) return null;
    const grp = (g: string) => (g === "Equity" ? "Equity" : g === "Fixed Income" ? "Fixed Income" : "Multi-asset, alternatives & cash");
    const groups = ["Equity", "Fixed Income", "Multi-asset, alternatives & cash"];
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => `${p.data[3]}<br/>Return ${pct(p.data[1])} · Vol ${pct(p.data[0])}` },
      xAxis: axis({ type: "value", name: "Volatility", nameLocation: "middle", nameGap: 24, axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      yAxis: axis({ type: "value", name: "Return p.a.", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      series: groups.map((g) => ({ name: g, type: "scatter", symbolSize: (v: any) => Math.max(8, Math.min(28, Math.sqrt(v[2] / 1e7))),
        itemStyle: { borderColor: tk.surface, borderWidth: 2, opacity: 0.85 },
        data: sc.data.data.points.filter((p: any) => grp(p.group) === g).map((p: any) => [p.volatility, p.return, p.size, p.name]) })) };
  }, [sc.data, tk]);
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <ChartCard id="relative_return" title="12-month relative return by fund (gross of fees)" subtitle="Sorted; hover for fund and benchmark returns" option={opt} loading={q.isLoading} error={q.error}
        lineage={q.data?.lineage} rows={q.data?.data.funds.map((f: any) => ({ fund: f.name, return_12m: f.return_12m, benchmark_12m: f.benchmark_12m }))} />
      <ChartCard id="relative_return" title="Risk-return (24 months, annualized)" subtitle="Bubble size = AUM; three groups (validated palette cap)" option={scOpt} loading={sc.isLoading} error={sc.error}
        lineage={sc.data?.lineage} rows={sc.data?.data.points} />
    </div>
  );
}

function Risk() {
  const { can } = useApp();
  const conc = useQuery({ queryKey: ["conc"], queryFn: () => api("/api/investment/concentration") });
  const corr = useQuery({ queryKey: ["corr"], queryFn: () => api("/api/investment/correlation"), enabled: can("risk:read") });
  const tk = tokens();
  const c = conc.data?.data;
  const concOpt = useMemo(() => c && ({ ...baseOption(), grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
    tooltip: { ...baseOption().tooltip, trigger: "axis", formatter: (p: any) => { const r = c.top_holdings[p[0].dataIndex]; return `${r.name}<br/>${pct(r.weight)} of portfolio assets<br/>held in ${r.portfolios_holding} portfolios`; } },
    yAxis: axis({ type: "category", inverse: true, data: c.top_holdings.map((h: any) => h.name.replace(" (SYN)", "")) }), xAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 1) } }),
    series: [{ type: "bar", data: c.top_holdings.map((h: any) => h.weight), itemStyle: { color: tk.series[0], borderRadius: [0, 4, 4, 0] }, label: { show: true, position: "right", color: tk.ink, formatter: (p: any) => pct(p.value, 1) } }] }), [c, tk]);
  const sectOpt = useMemo(() => c && ({ ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => `${p.name}: ${pct(p.data.w)} (CAD ${compact(p.value)})` },
    series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, itemStyle: { borderColor: tk.surface, gapWidth: 2 }, levels: [{ color: tk.seq.slice(1) }], colorMappingBy: "value",
      label: { color: "#fff", formatter: (p: any) => `${p.name}\n${pct(p.data.w, 1)}` }, data: c.sector_exposure.map((s: any) => ({ name: s.sector, value: s.value, w: s.weight })) }] }), [c, tk]);
  const corrOpt = useMemo(() => {
    const d = corr.data?.data;
    if (!d) return null;
    const cells: number[][] = [];
    d.matrix.forEach((r: number[], i: number) => r.forEach((v: number, j: number) => cells.push([j, i, v])));
    return { ...baseOption(), grid: { left: 10, right: 10, top: 10, bottom: 60, containLabel: true }, tooltip: { ...baseOption().tooltip, formatter: (p: any) => `${d.labels[p.data[1]]} × ${d.labels[p.data[0]]}: ${p.data[2].toFixed(2)}` },
      xAxis: axis({ type: "category", data: d.labels, axisLabel: { rotate: 45, color: tk.muted, fontSize: 9 } }), yAxis: axis({ type: "category", data: d.labels, axisLabel: { color: tk.muted, fontSize: 9 } }),
      visualMap: { min: -1, max: 1, calculable: false, orient: "horizontal", left: "center", bottom: 0, inRange: { color: tk.div }, textStyle: { color: tk.muted }, itemHeight: 120 },
      series: [{ type: "heatmap", data: cells, itemStyle: { borderColor: tk.surface, borderWidth: 1 } }] };
  }, [corr.data, tk]);
  if (conc.isLoading) return <Spinner />;
  if (conc.error) return <ErrorState error={conc.error} />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Portfolio assets analysed" value={`CAD ${compact(c.total_portfolio_aum)}`} sub={`${c.portfolio_count} portfolios`} />
        <Stat label="Top-10 issuer weight" value={pct(c.top10_weight)} /><Stat label="Effective issuers (1/HHI)" value={num(c.effective_n, 1)} />
        <Stat label="Portfolios above 10% issuer limit" value={c.portfolios_breaching_single_issuer_limit} tone="warn" sub="CTL-CONC-01" />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard id="concentration" title="Largest issuer exposures (all portfolios)" option={concOpt} height={360} lineage={conc.data.lineage} rows={c.top_holdings} />
        <ChartCard id="concentration" title="Sector exposure" option={sectOpt} height={360} rows={c.sector_exposure} />
        {can("risk:read") ? <ChartCard id="correlation" title="Sector correlation heatmap (24 months)" subtitle="Diverging scale centred on zero" option={corrOpt} height={380} lineage={corr.data?.lineage} loading={corr.isLoading} error={corr.error} />
          : <p className="text-sm text-muted">Correlation analytics require risk:read.</p>}
      </div>
    </div>
  );
}

function Market() {
  const q = useQuery({ queryKey: ["market"], queryFn: () => api("/api/investment/market"), retry: false });
  const tk = tokens();
  const d = q.data?.data;
  const opts = useMemo(() => d && ({
    lines: { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v) }, xAxis: axis({ type: "category", data: d.months.map(month) }),
      yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }), legend: { ...baseOption().legend, type: "scroll" },
      series: d.benchmarks.map((b: any) => ({ name: b.name.replace("FLO Synthetic ", ""), type: "line", data: b.series, symbol: "none", lineStyle: { width: 2 } })) },
    sect: { ...baseOption(), grid: { left: 10, right: 40, top: 10, bottom: 10, containLabel: true }, tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v) },
      yAxis: axis({ type: "category", data: Object.keys(d.sector_last_month) }), xAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      series: [{ type: "bar", data: Object.values(d.sector_last_month).map((v: any) => ({ value: v, itemStyle: { color: v >= 0 ? tk.series[2] : tk.series[1], borderRadius: 3 } })) }] },
  }), [d, tk]);
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="xl:col-span-2"><ChartCard id="benchmarks" title="Benchmark cumulative returns" option={opts?.lines} height={340} lineage={q.data.lineage}
        rows={d.benchmarks.map((b: any) => ({ benchmark: b.name, last_month: b.last_month, three_month: b.three_month, ytd: b.ytd, twelve_month: b.twelve_month, volatility: b.volatility }))} /></div>
      <ChartCard id="benchmarks" title="Sector returns, latest month" option={opts?.sect} height={340} />
      <ChartCard id="benchmarks" title="Top gainers / losers (latest month)">
        <div className="grid grid-cols-2 gap-3 text-xs">
          <ul>{d.top_gainers.map((m: any) => <li key={m.name} className="flex justify-between gap-2"><span className="truncate">{m.name}</span><span className="text-pos">{pct(m.last_month)}</span></li>)}</ul>
          <ul>{d.top_losers.map((m: any) => <li key={m.name} className="flex justify-between gap-2"><span className="truncate">{m.name}</span><span className="text-crit">{pct(m.last_month)}</span></li>)}</ul>
        </div>
      </ChartCard>
    </div>
  );
}

function Geo() {
  const [scope, setScope] = useState("enterprise");
  const q = useQuery({ queryKey: ["geo", scope], queryFn: () => api(`/api/executive/geographic-exposure?scope=${scope}`) });
  return (
    <ChartCard id="geographic_exposure" title="Geographic exposure map" lineage={q.data?.lineage} rows={q.data?.data.countries} loading={q.isLoading} error={q.error}
      actions={<Select aria-label="Exposure scope" className="h-7 text-xs" value={scope} onChange={(e) => setScope(e.target.value)}>
        <option value="enterprise">Enterprise (funds + portfolios)</option><option value="products">Funds</option><option value="portfolios">Managed portfolios</option></Select>}>
      {q.data && <GeoMap rows={q.data.data.countries} height={420} />}
    </ChartCard>
  );
}
