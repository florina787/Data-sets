import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ChartCard, DataGrid } from "@/components/ChartCard";
import { EChart } from "@/components/EChart";
import { GeoMap, type GeoRow } from "@/components/GeoMap";
import { Badge, Button, ErrorState, PageHeader, Progress, Select, Spinner, Stat } from "@/components/ui";
import { api, download, type WithLineage } from "@/lib/api";
import { useApp } from "@/lib/app";
import { axis, baseOption, tokens } from "@/lib/chartTheme";
import { bn, compact, human, mn, month, pct } from "@/lib/format";

const q = (path: string) => () => api<WithLineage<any>>(path);

export default function Executive() {
  const { filters, setFilters } = useApp();
  const m = filters.months;
  const f = `${filters.asset_class ? `&asset_class=${encodeURIComponent(filters.asset_class)}` : ""}${filters.vehicle ? `&vehicle=${encodeURIComponent(filters.vehicle)}` : ""}`;
  const [groupBy, setGroupBy] = useState("asset_class");
  const [flowGroup, setFlowGroup] = useState("vehicle");
  const [treeFocus, setTreeFocus] = useState<string | null>(null);
  const [heatCell, setHeatCell] = useState<[number, number] | null>(null);
  const [country, setCountry] = useState<GeoRow | null>(null);
  const kpis = useQuery({ queryKey: ["kpis", m], queryFn: q(`/api/executive/kpis?months=${m}`) });
  const trend = useQuery({ queryKey: ["trend", groupBy, f], queryFn: q(`/api/executive/aum-trend?months=24&group_by=${groupBy}${f}`) });
  const wf = useQuery({ queryKey: ["wf", m, f], queryFn: q(`/api/executive/aum-waterfall?months=${m}${f}`) });
  const re = useQuery({ queryKey: ["re"], queryFn: q(`/api/executive/revenue-expenses?months=24`) });
  const nf = useQuery({ queryKey: ["nf", flowGroup, f], queryFn: q(`/api/executive/net-flows?months=24&group_by=${flowGroup}${f}`) });
  const prof = useQuery({ queryKey: ["prof", m], queryFn: q(`/api/executive/product-profitability?months=${m}`) });
  const margin = useQuery({ queryKey: ["margin"], queryFn: q(`/api/executive/margin-trend?months=24`) });
  const attr = useQuery({ queryKey: ["attr"], queryFn: q(`/api/executive/revenue-attribution?months=12`) });
  const heat = useQuery({ queryKey: ["heat"], queryFn: q(`/api/executive/risk-heatmap`) });
  const geo = useQuery({ queryKey: ["geo"], queryFn: q(`/api/executive/geographic-exposure`) });
  const bud = useQuery({ queryKey: ["bud", m], queryFn: q(`/api/executive/actual-vs-budget?months=${m}`) });
  const init = useQuery({ queryKey: ["init"], queryFn: q(`/api/executive/initiatives`) });
  const ret = useQuery({ queryKey: ["ret"], queryFn: q(`/api/executive/retention`) });
  const tk = tokens();
  const k = kpis.data?.data;

  const trendOpt = useMemo(() => {
    const d = trend.data?.data;
    if (!d) return null;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `CAD ${compact(v)}` },
      xAxis: axis({ type: "category", data: d.months.map(month), boundaryGap: false }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: (v: number) => compact(v) } }),
      series: d.series.map((s: any) => ({ name: s.name, type: "line", stack: "aum", areaStyle: { opacity: 0.55 }, symbol: "none", lineStyle: { width: 2 }, emphasis: { focus: "series" }, data: s.values })) };
  }, [trend.data, tk.muted]);

  const wfOpt = useMemo(() => {
    const d = wf.data?.data;
    if (!d) return null;
    const v = d.steps.map((s: any) => Number(s.value));
    let run = 0;
    const base: number[] = [], val: number[] = [];
    v.forEach((x: number, i: number) => {
      if (i === 0 || i === v.length - 1) { base.push(0); val.push(x); run = i === 0 ? x : run; }
      else { base.push(x >= 0 ? run : run + x); val.push(Math.abs(x)); run += x; }
    });
    const colors = d.steps.map((s: any) => (s.kind === "total" ? tk.series[0] : s.kind === "increase" ? tk.series[2] : tk.series[1]));
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", formatter: (p: any) => `${p[1].name}: CAD ${compact(v[p[1].dataIndex])}` },
      xAxis: axis({ type: "category", data: d.steps.map((s: any) => s.step), axisLabel: { interval: 0, color: tk.muted } }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
      series: [{ type: "bar", stack: "w", itemStyle: { color: "transparent" }, data: base, silent: true },
        { type: "bar", stack: "w", barWidth: "45%", data: val.map((x, i) => ({ value: x, itemStyle: { color: colors[i], borderRadius: 4 } })),
          label: { show: true, position: "top", color: tk.ink, formatter: (p: any) => compact(v[p.dataIndex]) } }] };
  }, [wf.data, tk]);

  const reOpt = useMemo(() => {
    const d = re.data?.data;
    if (!d) return null;
    const lines = Object.keys(d.expenses);
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `CAD ${compact(v)}` },
      xAxis: axis({ type: "category", data: d.months.map(month) }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
      series: [...lines.map((l) => ({ name: human(l), type: "bar", stack: "exp", data: d.expenses[l], barWidth: "55%", itemStyle: { borderColor: tk.surface, borderWidth: 1 } })),
        { name: "Revenue", type: "line", data: d.revenue, symbol: "circle", symbolSize: 6, lineStyle: { width: 2, color: tk.ink }, itemStyle: { color: tk.ink } }] };
  }, [re.data, tk]);

  const nfOpt = useMemo(() => {
    const d = nf.data?.data;
    if (!d) return null;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `CAD ${compact(v)}` },
      xAxis: axis({ type: "category", data: d.months.map(month) }), yAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
      series: d.series.map((s: any) => ({ name: s.name, type: "bar", stack: "net", data: s.net, itemStyle: { borderColor: tk.surface, borderWidth: 1 } })) };
  }, [nf.data, tk]);

  const treeOpt = useMemo(() => {
    const d = prof.data?.data;
    if (!d) return null;
    const groups = treeFocus ? d.tree.filter((g: any) => g.name === treeFocus) : d.tree;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, formatter: (p: any) => p.data.margin != null ? `${p.name}<br/>Revenue CAD ${compact(p.value)}<br/>Contribution margin ${pct(p.data.margin)}<br/>Fee ${p.data.fee_bps} bps` : `${p.name}: CAD ${compact(p.value)}` },
      visualMap: { show: true, type: "continuous", min: -0.4, max: 0.6, dimension: 1, inRange: { color: tk.div }, text: ["High margin", "Negative"], textStyle: { color: tk.muted }, orient: "horizontal", left: "center", bottom: 0, itemHeight: 120 },
      series: [{ type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false }, top: 10, bottom: 40, left: 0, right: 0, itemStyle: { borderColor: tk.surface, gapWidth: 2 },
        levels: [{ itemStyle: { borderWidth: 3, gapWidth: 3 }, upperLabel: { show: true, color: tk.ink, height: 18 } }, {}],
        data: groups.map((g: any) => ({ name: g.name, children: g.children.map((c: any) => ({ name: c.name.replace(" (SYN)", ""), value: [c.revenue, c.margin ?? 0], margin: c.margin, fee_bps: c.fee_bps })) })) }] };
  }, [prof.data, treeFocus, tk]);

  const marginOpt = useMemo(() => {
    const d = margin.data?.data;
    if (!d) return null;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => pct(v, 1) },
      xAxis: axis({ type: "category", data: d.months.map(month) }), yAxis: axis({ type: "value", scale: true, axisLabel: { color: tk.muted, formatter: (v: number) => pct(v, 0) } }),
      series: [{ name: "Operating margin", type: "line", data: d.operating_margin, symbolSize: 6, lineStyle: { width: 2 }, markLine: { silent: true, symbol: "none", lineStyle: { color: tk.muted, type: "dashed" }, data: [{ type: "average", name: "avg" }], label: { color: tk.muted, formatter: (p: any) => `avg ${pct(p.value, 1)}` } } }] };
  }, [margin.data, tk]);

  const yieldOpt = useMemo(() => {
    const d = margin.data?.data;
    if (!d) return null;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis", valueFormatter: (v: number) => `${v.toFixed(1)} bps` },
      xAxis: axis({ type: "category", data: d.months.map(month) }), yAxis: axis({ type: "value", scale: true, axisLabel: { color: tk.muted, formatter: (v: number) => `${v}` } }),
      series: [{ name: "Revenue yield (bps)", type: "line", data: d.revenue_yield_bps, symbolSize: 6, lineStyle: { width: 2, color: tk.series[1] }, itemStyle: { color: tk.series[1] } }] };
  }, [margin.data, tk]);

  const heatOpt = useMemo(() => {
    const d = heat.data?.data;
    if (!d) return null;
    const cells: number[][] = [];
    d.grid.forEach((row: number[], i: number) => row.forEach((n: number, j: number) => cells.push([j, i, n])));
    return { ...baseOption(), grid: { left: 70, right: 10, top: 10, bottom: 50, containLabel: true },
      tooltip: { ...baseOption().tooltip, formatter: (p: any) => `Likelihood ${p.data[0] + 1} × Impact ${p.data[1] + 1}: ${p.data[2]} risk(s)` },
      xAxis: axis({ type: "category", name: "Likelihood", nameLocation: "middle", nameGap: 26, data: [1, 2, 3, 4, 5], splitArea: { show: false } }),
      yAxis: axis({ type: "category", name: "Impact", nameLocation: "middle", nameGap: 30, data: [1, 2, 3, 4, 5] }),
      visualMap: { min: 0, max: Math.max(1, ...cells.map((c) => c[2])), show: false, inRange: { color: tk.seq } },
      series: [{ type: "heatmap", data: cells, label: { show: true, color: tk.ink }, itemStyle: { borderColor: tk.surface, borderWidth: 2, borderRadius: 4 } }] };
  }, [heat.data, tk]);

  const budOpt = useMemo(() => {
    const d = bud.data?.data;
    if (!d) return null;
    return { ...baseOption(), grid: { left: 150, right: 20, top: 10, bottom: 20, containLabel: false },
      tooltip: { ...baseOption().tooltip, trigger: "axis", formatter: (p: any) => { const r = d.lines[p[0].dataIndex]; return `${human(r.line)}<br/>Actual ${mn(r.actual)}<br/>Budget ${mn(r.budget)}<br/>Variance ${mn(r.variance)} (${r.favourable ? "favourable" : "unfavourable"})`; } },
      yAxis: axis({ type: "category", data: d.lines.map((l: any) => human(l.line)) }), xAxis: axis({ type: "value", axisLabel: { color: tk.muted, formatter: compact } }),
      series: [{ type: "bar", barWidth: "55%", data: d.lines.map((l: any) => ({ value: l.variance, itemStyle: { color: l.favourable ? tk.series[2] : tk.series[1], borderRadius: 4 } })),
        label: { show: true, position: "right", color: tk.ink, formatter: (p: any) => `${p.value >= 0 ? "+" : ""}${compact(p.value)}` } }] };
  }, [bud.data, tk]);

  const retOpt = useMemo(() => {
    const d = ret.data?.data;
    if (!d) return null;
    return { ...baseOption(), tooltip: { ...baseOption().tooltip, trigger: "axis" }, xAxis: axis({ type: "category", data: d.series.map((x: any) => month(x.month)) }),
      yAxis: axis({ type: "value" }), series: [{ name: "Closures", type: "bar", data: d.series.map((x: any) => x.closures), itemStyle: { color: tk.series[1], borderRadius: [4, 4, 0, 0] } }] };
  }, [ret.data, tk]);

  const heatItems = heatCell && heat.data ? heat.data.data.items.filter((r: any) => r.likelihood === heatCell[0] + 1 && r.impact === heatCell[1] + 1) : [];

  return (
    <div className="space-y-4">
      <PageHeader title="Executive Command Center" subtitle={`Trailing ${m} months · CAD · synthetic data${filters.asset_class ? ` · filtered: ${filters.asset_class}` : ""}`}
        actions={<>
          {(filters.asset_class || filters.vehicle) && <Button size="sm" onClick={() => setFilters({ asset_class: "", vehicle: "" })}>Clear filters</Button>}
          <Button size="sm" onClick={() => download(`/api/exports/kpis.csv?months=${m}`, "flo-kpis.csv")}>Export KPIs</Button>
          <Button size="sm" onClick={() => download(`/api/exports/board-report.html?months=${m}`, "flo-board-report.html")}>Board report</Button>
        </>} />
      {kpis.error ? <ErrorState error={kpis.error} /> : !k ? <Spinner /> : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-6">
          <Stat label="Total AUM" value={bn(k.total_aum)} sub={`${pct(k.aum_growth)} vs period start`} tone={k.aum_growth >= 0 ? "good" : "crit"} />
          <Stat label="Net client flows" value={bn(k.net_flows)} sub={`subs ${bn(k.subscriptions)} · reds ${bn(k.redemptions)}`} />
          <Stat label="Fee-earning assets" value={bn(k.fee_earning_assets)} sub={`${pct(k.fee_earning_assets / k.total_aum, 1)} of AUM`} />
          <Stat label="Management fee revenue" value={mn(k.management_fee_revenue)} sub={`yield ${k.revenue_yield_bps.toFixed(1)} bps (prior ${k.prior_period?.revenue_yield_bps.toFixed(1)})`} />
          <Stat label="Operating expenses" value={mn(k.operating_expenses)} sub={k.prior_period ? `${pct(k.operating_expenses / k.prior_period.operating_expenses - 1)} vs prior` : ""} tone="warn" />
          <Stat label="Operating margin" value={pct(k.operating_margin)} sub={k.prior_period ? `prior ${pct(k.prior_period.operating_margin)}` : ""} tone={k.prior_period && k.operating_margin < k.prior_period.operating_margin ? "crit" : "good"} />
          <Stat label="Client retention" value={pct(k.client_retention, 1)} sub="12-month, synthetic CRM" />
          <Stat label="Market movement" value={bn(k.market_movement)} sub="AUM change not from flows" />
          <Stat label="High enterprise risks" value={k.enterprise_risk.high_risks} sub={`${k.enterprise_risk.open_critical_compliance} open high/critical exceptions`} tone="warn" />
          <Stat label="Initiatives behind" value={`${k.initiatives.behind} / ${k.initiatives.count}`} sub={`avg progress ${k.initiatives.avg_progress}%`} />
          <Stat label="Revenue reconciliation" value={k.revenue_reconciliation.balanced ? "Balanced" : "Break"} sub="ledger vs product accruals" tone={k.revenue_reconciliation.balanced ? "good" : "crit"} />
          <Stat label="Operating income" value={mn(k.operating_income)} />
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard id="aum_trend" title="1 · AUM historical trend" subtitle="Click a series to filter the dashboard by asset class" lineage={trend.data?.lineage}
          option={trendOpt} loading={trend.isLoading} error={trend.error} onClick={(p) => groupBy === "asset_class" && setFilters({ asset_class: p.seriesName })}
          rows={trend.data?.data.months.map((mm: string, i: number) => ({ month: mm, ...Object.fromEntries(trend.data!.data.series.map((s: any) => [s.name, s.values[i]])) }))}
          actions={<Select aria-label="Group AUM by" className="h-7 text-xs" value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="asset_class">by asset class</option><option value="vehicle">by vehicle</option><option value="region">by region</option></Select>} />
        <ChartCard id="aum_waterfall" title="2 · AUM attribution waterfall" subtitle={wf.data ? `${wf.data.data.period[0]} → ${wf.data.data.period[1]} · reconciliation ${wf.data.data.reconciliation.balanced ? "balanced to the cent" : "BREAK"} (${wf.data.data.reconciliation.checked_rows} product-months)` : ""}
          lineage={wf.data?.lineage} option={wfOpt} loading={wf.isLoading} error={wf.error} rows={wf.data?.data.by_asset_class} />
        <ChartCard id="revenue_expenses" title="3 · Revenue and expenses" subtitle="Monthly GL actuals; stacked expenses vs revenue line (one CAD axis)" lineage={re.data?.lineage}
          option={reOpt} loading={re.isLoading} error={re.error} rows={re.data?.data.months.map((mm: string, i: number) => ({ month: mm, revenue: re.data!.data.revenue[i], total_expenses: re.data!.data.total_expenses[i], operating_income: re.data!.data.operating_income[i] }))} />
        <ChartCard id="net_flows" title="4 · Net flow analysis" subtitle="Click a bar to filter by that group" lineage={nf.data?.lineage} option={nfOpt} loading={nf.isLoading} error={nf.error}
          onClick={(p) => flowGroup === "vehicle" ? setFilters({ vehicle: p.seriesName }) : flowGroup === "asset_class" && setFilters({ asset_class: p.seriesName })}
          rows={nf.data ? Object.entries(nf.data.data.net_by_group).map(([g, v]) => ({ group: g, net_flows_24m: v as number })) : undefined}
          actions={<Select aria-label="Group flows by" className="h-7 text-xs" value={flowGroup} onChange={(e) => setFlowGroup(e.target.value)}>
            <option value="vehicle">by vehicle</option><option value="asset_class">by asset class</option><option value="strategy">by strategy</option></Select>} />
        <ChartCard id="product_profitability" title="5 · Product profitability" subtitle={treeFocus ? `Drilled into ${treeFocus} — click to go back` : "Size = revenue, colour = contribution margin (diverging). Click a group to drill down."}
          lineage={prof.data?.lineage} option={treeOpt} height={320} loading={prof.isLoading} error={prof.error} onClick={(p) => setTreeFocus(treeFocus ? null : (p.treePathInfo?.[1]?.name ?? null))}
          rows={prof.data?.data.tree.flatMap((g: any) => g.children.map((c: any) => ({ asset_class: g.name, ...c })))} />
        <div className="grid gap-4">
          <ChartCard id="margin_trend" title="6 · Operating margin trend" lineage={margin.data?.lineage} option={marginOpt} height={170} loading={margin.isLoading} error={margin.error}
            rows={margin.data?.data.months.map((mm: string, i: number) => ({ month: mm, operating_margin: margin.data!.data.operating_margin[i], revenue_yield_bps: margin.data!.data.revenue_yield_bps[i] }))} />
          <ChartCard id="margin_trend" title="Revenue yield (bps)" subtitle={attr.data ? `Revenue change ${mn(attr.data.data.change)}: volume ${mn(attr.data.data.volume_effect)}, mix ${mn(attr.data.data.mix_effect)}, fee changes ${mn(attr.data.data.fee_change_effect)}` : ""}
            lineage={attr.data?.lineage} option={yieldOpt} height={150} loading={margin.isLoading} />
        </div>
        <ChartCard id="risk_heatmap" title="7 · Enterprise risk heatmap" subtitle="Click a cell to list the risks" lineage={heat.data?.lineage} option={heatOpt} loading={heat.isLoading} error={heat.error}
          onClick={(p) => setHeatCell([p.data[0], p.data[1]])} rows={heat.data?.data.items.map((r: any) => ({ id: r.id, category: r.category, title: r.title, likelihood: r.likelihood, impact: r.impact, score: r.score, trend: r.trend }))}>
          {heatOpt && <div>{/* chart + drill list */}
            <ChartBody option={heatOpt} onClick={(p) => setHeatCell([p.data[0], p.data[1]])} label="Enterprise risk heatmap" />
            {heatItems.length > 0 && <ul className="mt-2 space-y-1 text-xs">{heatItems.map((r: any) => <li key={r.id}><Badge tone="warn">{r.category}</Badge> {r.title} · owner {r.owner} · {r.trend}</li>)}</ul>}
          </div>}
        </ChartCard>
        <ChartCard id="geographic_exposure" title="8 · Geographic investment exposure" subtitle={country ? `${country.country} (${country.region}): CAD ${compact(country.value)} · ${pct(country.weight)}` : "Look-through by issuer country; click a country for detail"}
          lineage={geo.data?.lineage} loading={geo.isLoading} error={geo.error} rows={geo.data?.data.countries}>
          {geo.data && <GeoMap rows={geo.data.data.countries} onSelect={setCountry} />}
        </ChartCard>
        <ChartCard id="actual_vs_budget" title="9 · Actual versus budget (variance)" subtitle="Green favourable · orange unfavourable; hover for actual/budget" lineage={bud.data?.lineage} option={budOpt} loading={bud.isLoading} error={bud.error} rows={bud.data?.data.lines} />
        <ChartCard id="initiative_scorecard" title="10 · Strategic initiative scorecard" subtitle="Bar = reported progress; tick = time-elapsed plan" lineage={init.data?.lineage} loading={init.isLoading} error={init.error} rows={init.data?.data.initiatives}>
          {init.data && <div className="max-h-[300px] space-y-2 overflow-y-auto scroll-thin pr-1">{init.data.data.initiatives.map((i: any) => (
            <div key={i.id} className="text-xs"><div className="flex justify-between gap-2"><span>{i.name} <span className="text-muted">· {i.owner}</span></span>
              <Badge tone={i.status === "behind" ? "warn" : i.status === "complete" ? "good" : "blue"}>{i.status.replace("_", " ")}</Badge></div>
              <Progress value={i.progress_pct} planned={i.planned_progress_pct} /></div>))}</div>}
        </ChartCard>
        <ChartCard id="retention" title="Client retention (closures per month)" lineage={ret.data?.lineage} option={retOpt} height={200} loading={ret.isLoading} error={ret.error} rows={ret.data?.data.series} />
      </div>
      {attr.data && <ChartCard id="product_profitability" title="Revenue mix by vehicle" subtitle="AUM share and realized yield, prior vs current 12 months"><DataGrid rows={attr.data.data.mix_by_vehicle} /></ChartCard>}
    </div>
  );
}

function ChartBody({ option, onClick, label }: { option: any; onClick: (p: any) => void; label: string }) {
  return <EChart option={option} onClick={onClick} ariaLabel={label} height={260} />;
}
