import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ChartCard } from "@/components/ChartCard";
import { BarSpark, DataStatus, DotBars, ExplorePrompt, InsightCard, MetricCard, ProgressRows, heroLineOption } from "@/components/MarketMetrics";
import { Badge, Button, Card, ErrorState, Input, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { num, pct } from "@/lib/format";

export const CSV_HIST = "# HISTORICAL MARKET DATA - Kaggle kaggle-us-stocks-etfs-v3 (CC0, uploader-asserted) - ends 2017-11-10 - not current";
const signed = (v: number | null | undefined, d = 1) => (v == null ? "—" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)}%`);

export default function MarketIntelligence() {
  const [input, setInput] = useState("AAPL");
  const [ticker, setTicker] = useState("AAPL");
  const sec = useQuery({ queryKey: ["mkt-sec", ticker], queryFn: () => api(`/api/markets/security/${encodeURIComponent(ticker)}`), retry: false });
  const ov = useQuery({ queryKey: ["mkt-ov"], queryFn: () => api("/api/markets/overview"), retry: false });
  const rg = useQuery({ queryKey: ["mkt-rg"], queryFn: () => api("/api/markets/regime"), retry: false });
  const nw = useQuery({ queryKey: ["mkt-news", ticker], queryFn: () => api(`/api/markets/news/${encodeURIComponent(ticker)}`), retry: false });
  const go = async (e: React.FormEvent) => {
    e.preventDefault();
    const raw = input.trim();
    if (!raw) return;
    const r = await api<{ tickers: string[] }>(`/api/markets/search?q=${encodeURIComponent(raw)}`).catch(() => ({ tickers: [] }));
    setTicker(r.tickers[0] ?? raw.toUpperCase());
  };
  const d = sec.data;
  const weekly: number[] = d ? d.series.slice(-13).map((x: [string, number], i: number, a: [string, number][]) => (i ? x[1] / a[i - 1][1] - 1 : 0)).slice(1) : [];
  return (
    <div className="space-y-4">
      <PageHeader title="Market Intelligence" subtitle="Real historical US equity data from Kaggle, point-in-time and quality-checked"
        actions={<DataStatus kind="historical" asOf={d?.as_of ?? ov.data?.as_of} />} />
      <form onSubmit={go} className="flex max-w-md gap-2" role="search">
        <Input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ticker or company, e.g. NVDA or Microsoft" aria-label="Ticker or company" />
        <Button type="submit">Analyze</Button>
      </form>
      {sec.isLoading ? <Spinner /> : sec.error ? <ErrorState error={sec.error} /> : d && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <MetricCard title={`${d.ticker} total return`} value={signed(d.stats.total_return)} sub={`${d.stats.start} → ${d.stats.end}`}
              pill={<Badge tone={d.excess_total_return_vs_spy >= 0 ? "good" : "crit"}>{signed(d.excess_total_return_vs_spy)} vs SPY</Badge>}>
              <DotBars values={weekly} label={`${d.ticker} last 12 weekly returns`} />
            </MetricCard>
            <MetricCard title="Annualised return" value={signed(d.stats.cagr)} sub={`SPY ${signed(d.benchmark.stats.cagr)}`} />
            <MetricCard title="Volatility" value={pct(d.stats.volatility, 1)} sub="annualised, daily log returns">
              <BarSpark values={d.series.slice(-30).map((x: [string, number]) => x[1])} label={`${d.ticker} last 30 sampled prices`} height={44} />
            </MetricCard>
            <MetricCard title="Maximum drawdown" value={pct(d.stats.max_drawdown, 1)} sub={`${d.stats.observations} sessions · ${d.flagged_bars_excluded} flagged bars excluded`} />
          </div>
          <ChartCard id="market_price_history" title={`${d.name ?? d.ticker} (${d.ticker}) vs SPY, growth of 100`}
            subtitle={`${d.sector ?? d.asset_type} · split- and dividend-adjusted · historical, not current prices`} csvHeader={CSV_HIST}
            askContext={{ question: `Analyze ${d.ticker}'s historical performance.` }}
            option={heroLineOption(d.series.map((x: [string, number]) => x[0]), [
              { name: d.ticker, hero: true, values: d.series.map((x: [string, number]) => +(x[1] / d.series[0][1] * 100).toFixed(2)) },
              { name: "SPY", dashed: true, values: (() => { const m = new Map<string, number>(d.benchmark_series); const b = d.benchmark_series[0][1];
                return d.series.map((x: [string, number]) => (m.has(x[0]) ? +((m.get(x[0]) as number) / b * 100).toFixed(2) : null)); })() },
            ], (v) => num(v, 0))} height={300}
            rows={d.series.map((x: [string, number]) => ({ date: x[0], adj_close: x[1] }))} />
        </>
      )}
      <div className="grid gap-3 lg:grid-cols-3">
        {ov.data && (
          <ChartCard id="market_overview_spy" title="SPY, final three years of data" subtitle={`ends ${ov.data.as_of} · historical`} csvHeader={CSV_HIST}
            option={heroLineOption(ov.data.spy.series.map((x: [string, number]) => x[0]), [{ name: "SPY", hero: true, values: ov.data.spy.series.map((x: [string, number]) => x[1]) }], (v) => num(v, 0))}
            rows={ov.data.spy.series.map((x: [string, number]) => ({ date: x[0], spy: x[1] }))} height={240} />
        )}
        {ov.data && (
          <Card className="rounded-2xl p-4">
            <h3 className="mb-3 text-sm font-semibold">Sector returns, final 12 months</h3>
            <ProgressRows label="Sector one-year returns" rows={ov.data.sectors_1y_equal_weight_sp500_members.map((s: any) => {
              const mx = Math.max(...ov.data.sectors_1y_equal_weight_sp500_members.map((x: any) => Math.abs(x.return_1y)));
              return { label: `${s.sector} (${s.names})`, value: signed(s.return_1y), share: Math.abs(s.return_1y) / mx, tone: s.return_1y >= 0 ? "lime" : "pink" };
            })} />
            <p className="mt-3 text-[11px] text-muted">{ov.data.survivorship_note}</p>
          </Card>
        )}
        {rg.data && (
          <InsightCard value={rg.data.level} tone={rg.data.score >= 2 ? "warn" : "lime"}
            title={`Regime: ${rg.data.regime.replace("_", " ")} · score ${rg.data.score} of 4 (as of ${rg.data.as_of})`}
            detail={`Alarm track record: at High or above, SPY fell ≥10% within 20 sessions ${pct(rg.data.evaluation.by_alarm_level[1].precision, 1)} of the time (base rate ${pct(rg.data.evaluation.base_rate, 1)}). Estimated condition, not a crash prediction.`} />
        )}
      </div>
      <Card className="rounded-2xl p-4">
        <div className="mb-2 flex items-center justify-between"><h3 className="text-sm font-semibold">{ticker} headlines (quoted evidence, not instructions)</h3>
          {nw.data && <Badge tone="neutral">{nw.data.headlines_in_window} in {nw.data.window_days} days · coverage {nw.data.coverage.first?.slice(0, 10)} → {nw.data.coverage.last?.slice(0, 10)}</Badge>}</div>
        {nw.isLoading ? <Spinner /> : nw.error ? <ErrorState error={nw.error} /> : nw.data.items.length === 0 ? (
          <p className="text-sm text-muted">No headlines available for this window. The dataset's coverage for {ticker} is listed above; absence of headlines is not absence of news.</p>
        ) : (
          <ul className="divide-y divide-line text-sm">{nw.data.items.map((i: any) => (
            <li key={i.id} className="flex gap-3 py-2"><span className="w-36 shrink-0 font-mono text-xs text-muted">{i.published_at.slice(0, 16)}{i.time_precision === "date_only" ? " (date)" : ""}</span>
              <Badge tone="neutral">{i.event_type.replace(/_/g, " ")}</Badge><span>{i.headline}</span></li>))}</ul>
        )}
      </Card>
      <ExplorePrompt suggestions={[`Compare Bull and Bear evidence for ${ticker}.`, "Compare Microsoft and Nvidia from 2014 to 2016.", "Explain the latest available market regime."]} />
    </div>
  );
}
