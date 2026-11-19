import { useQuery } from "@tanstack/react-query";
import { DataStatus, ExplorePrompt, InsightCard, MetricCard, ProgressRows } from "@/components/MarketMetrics";
import { Badge, Card, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { pct } from "@/lib/format";

export default function DataIntelligence() {
  const q = useQuery({ queryKey: ["mkt-datasets"], queryFn: () => api("/api/markets/datasets"), retry: false });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const d = q.data;
  const lake = d.research_lake;
  const v = lake?.validation;
  const flags = Object.entries(lake?.quality.flags ?? {}).filter(([k]) => k !== "ok") as [string, number][];
  const totalBars = lake?.quality.bars ?? 1;
  return (
    <div className="space-y-4">
      <PageHeader title="Data Intelligence" subtitle="Provenance, licences, checksums, coverage and known limitations of every market dataset"
        actions={<DataStatus kind="historical" asOf={lake?.counts.research_window[1]} />} />
      {lake && (
        <div className="grid gap-3 md:grid-cols-4">
          <MetricCard title="Research-window bars" value={lake.counts.research_window_bars.toLocaleString()} sub={`${lake.counts.research_window_tickers.toLocaleString()} tickers · ${lake.counts.sessions.toLocaleString()} sessions`} />
          <MetricCard title="Clean stock bars" value={lake.counts.research_window_clean_stock_bars.toLocaleString()} sub={`${lake.counts.research_window.join(" → ")}`} />
          <MetricCard title="Cross-source agreement" value={pct(v.cross_source_daily_returns.share_within_1pct, 1)}
            sub={`daily returns within 1% on ${v.cross_source_daily_returns.overlapping_ticker_days.toLocaleString()} ticker-days vs the NYSE dataset`} />
          <InsightCard value={String(lake.quality.score)} title="Data quality score (of 100)" detail={lake.quality.score_formula} />
        </div>
      )}
      <div className="grid gap-3 lg:grid-cols-2">
        {d.datasets.map((x: any) => (
          <Card key={x.dataset_id} className="rounded-2xl p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-sm font-semibold">{x.title}</h3>
              <div className="flex gap-1">{x.ingested ? <Badge tone="good">ingested</Badge> : <Badge tone="neutral">not ingested</Badge>}<Badge tone="gold">{x.kaggle_license}</Badge></div>
            </div>
            <dl className="mt-2 grid grid-cols-[9rem_1fr] gap-x-2 gap-y-1 text-xs">
              <dt className="text-muted">Source</dt><dd><a className="text-gold underline" href={x.url} target="_blank" rel="noreferrer">{x.kaggle_ref}</a> v{x.kaggle_version}</dd>
              <dt className="text-muted">Publisher</dt><dd>{x.publisher}</dd>
              <dt className="text-muted">Upstream</dt><dd>{x.upstream_source}</dd>
              <dt className="text-muted">Coverage</dt><dd>{x.coverage}</dd>
              <dt className="text-muted">Adjustment</dt><dd>{x.adjustment}</dd>
              {x.normalised && <><dt className="text-muted">Rows</dt><dd className="font-mono">{x.normalised.rows.toLocaleString()} ({x.normalised.start?.slice(0, 10)} → {x.normalised.end?.slice(0, 10)})</dd></>}
              {x.files && <><dt className="text-muted">Content SHA-256</dt><dd className="break-all font-mono">{x.files.content_sha256.slice(0, 24)}…</dd>
                <dt className="text-muted">Files</dt><dd>{x.files.canonical.toLocaleString()} canonical · {x.files.duplicates_skipped.toLocaleString()} duplicates · {x.files.empty_skipped} empty skipped</dd></>}
              <dt className="text-muted">Use</dt><dd>{x.use_restrictions}</dd>
            </dl>
            <ul className="mt-2 list-disc pl-5 text-xs text-muted">{x.known_limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
          </Card>
        ))}
      </div>
      {lake && (
        <div className="grid gap-3 lg:grid-cols-3">
          <Card className="rounded-2xl p-4">
            <h3 className="mb-3 text-sm font-semibold">Flagged bars (excluded, never deleted or filled)</h3>
            <ProgressRows label="Quality flags" rows={flags.map(([k, n]) => ({ label: k.replace(/_/g, " "), value: n.toLocaleString(), share: Math.max(0.02, n / Math.max(...flags.map((f) => f[1]))), tone: "pink" as const }))} />
            <p className="mt-2 text-xs text-muted">Missing sessions counted: {lake.quality.missing_sessions.toLocaleString()} of {totalBars.toLocaleString()} bars.</p>
          </Card>
          <Card className="rounded-2xl p-4 text-sm">
            <h3 className="mb-2 text-sm font-semibold">Survivorship evidence</h3>
            <p>{v.survivorship.sp500_2016_members_absent_from_primary} S&amp;P 500 (2016) members have no history at all: {v.survivorship.examples.join(", ")}.</p>
            <p className="mt-2 text-xs text-muted">Unadjusted corporate actions flagged: {v.unadjusted_corporate_actions_flagged.join(", ")}. Splits confirmed adjusted: {v.splits.primary_smooth_on_split_day} of {v.splits.detected_in_secondary}.</p>
          </Card>
          <Card className="rounded-2xl p-4 text-sm">
            <h3 className="mb-2 text-sm font-semibold">Current market feed</h3>
            <Badge tone={d.current_feed.scheduler_enabled ? "good" : "warn"}>{d.current_feed.scheduler_enabled ? "forward scheduler enabled" : "forward scheduler disabled"}</Badge>
            <ul className="mt-2 list-disc pl-5 text-xs text-muted">{d.current_feed.reasons.map((r: string) => <li key={r}>{r}</li>)}</ul>
          </Card>
        </div>
      )}
      <ExplorePrompt suggestions={["Which datasets are available?", "Show model accuracy over the holdout period."]} />
    </div>
  );
}
