import { useNavigate } from "react-router-dom";
import { ArrowRight, ExternalLink } from "lucide-react";
import { api, dsPath, filtersParam, type Breakdown, type CrossTab, type Filters } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { fmtInt, fmtPct } from "../lib/format";
import { Badge, Button, Card, ErrorBox, PageHeader, Spinner, Stat, Table } from "../components/ui";
import { ChartCard } from "../charts/ChartCard";
import { CohortComparison, ResolutionStacked, TopicBar, TopicSentimentHeatmap, VolumeSeries } from "../charts/charts";
import { ScopeChips } from "../assistant/Flo";

type OverviewData = {
  dataset: any; summary: any; topics: Breakdown; resolution: Breakdown; sentiment: Breakdown; escalation: Breakdown;
  handoff?: Breakdown; limitations: any; suggestions: { title: string; basis: string; question: string; filters: Filters; evidence: any[] }[];
};

function count(b: Breakdown | undefined, key: string) {
  return b?.items.find((i) => i.key === key)?.count ?? 0;
}

export function Overview() {
  const { filters, setFilters, ask, busy, dataset } = useApp();
  const nav = useNavigate();
  const p = (f: Filters) => ({ filters: filtersParam(f) });
  const ov = useData<OverviewData>((id, f) => api(dsPath(id, "overview"), { params: p(f) }));
  const xt = useData<CrossTab>((id, f) => api(dsPath(id, "crosstab"), { params: { rows: "primary_topic", cols: "resolution_status", ...p(f) } }));
  const hm = useData<CrossTab>((id, f) => api(dsPath(id, "crosstab"), { params: { rows: "primary_topic", cols: "sentiment_end", ...p(f) } }));
  const ts = useData<any>((id, f) => api(dsPath(id, "timeseries"), { params: { grain: "week", ...p(f) } }));
  const co = useData<any>((id, f) => api(dsPath(id, "cohorts"), { params: p(f) }));

  if (!dataset) return <PageHeader title="Executive overview" description="Select a dataset to begin." />;
  if (ov.error) return <ErrorBox onRetry={ov.reload}>{ov.error}</ErrorBox>;
  const d = ov.data;
  const toggleTopic = (k: string) => {
    const cur = filters.topics ?? [];
    setFilters({ ...filters, topics: cur.includes(k) ? cur.filter((x) => x !== k) : [k] });
  };
  const openExplorer = (f: Filters) => nav(`/explorer?filters=${encodeURIComponent(filtersParam(f) ?? "")}`);
  const n = d?.summary.denominator ?? 0;
  const unresolved = count(d?.resolution, "unresolved_explicit");
  const resUnknown = d?.resolution.unknown ?? 0;
  const esc = count(d?.escalation, "yes");
  const escUnknown = d?.escalation.unknown ?? 0;
  const scope = d?.summary.scope ?? "";
  const hasFilter = Object.values(filters).some((v) => (Array.isArray(v) ? v.length : v));

  return (
    <div className="space-y-5">
      <PageHeader
        title="Executive overview"
        description={<>{d?.dataset.name} · {d?.dataset.synthetic ? "synthetic demonstration fixtures" : `imported from ${d?.dataset.source}`} · labels: {d?.dataset.active_analysis.startsWith("rules") ? "rules-based (inferred)" : d?.dataset.active_analysis}</>}
        actions={hasFilter ? <Button size="sm" onClick={() => setFilters({})}>Clear all filters</Button> : undefined}
      />
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted"><span className="font-medium">Active scope:</span><ScopeChips /></div>
      {!d ? <Spinner /> : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Conversations in scope" value={fmtInt(n)} sub={`of ${fmtInt(d.dataset.conversations)} selected · ${fmtInt(d.summary.messages)} messages`} />
            <Stat label="Explicitly unresolved" tone="red" value={fmtInt(unresolved)} sub={`of ${fmtInt(n - resUnknown)} with known outcome (${fmtPct((n - resUnknown) ? unresolved / (n - resUnknown) : null)})`} />
            <Stat label="Customer-confirmed resolved" tone="green" value={fmtInt(count(d.resolution, "resolved_confirmed"))} sub={`of ${fmtInt(n - resUnknown)} with known outcome`} />
            <Stat label="Escalation requests" tone="amber" value={fmtInt(esc)} sub={`of ${fmtInt(n - escUnknown)} with known value · ${fmtInt(escUnknown)} unknown`} />
            <Stat label="Unknown outcome" value={fmtInt(resUnknown)} sub={`of ${fmtInt(n)} · no outcome evidence in thread`} />
          </div>
          {d.handoff && (
            <div className="rounded-[10px] border border-line bg-card px-4 py-3 text-sm">
              <span className="font-medium">Why are outcomes often unknown?</span>{" "}
              <span className="tnum">{fmtInt(count(d.handoff, "confirmed") + count(d.handoff, "requested"))}</span> of <span className="tnum">{fmtInt(n)}</span> conversations
              were moved to a private channel by support (<span className="tnum">{fmtInt(count(d.handoff, "confirmed"))}</span> with the customer confirming), so the outcome happens out of view.{" "}
              <button type="button" className="text-teal underline" onClick={() => setFilters({ ...filters, handoff: ["confirmed", "requested"] })}>Show these conversations</button>
              <span className="ml-1 text-xs text-muted">(observed from support messages such as “please DM us”)</span>
            </div>
          )}

          <Card title="Investigation suggestions" subtitle="Each suggestion is computed from the counts below and shows supporting messages.">
            <div className="grid gap-3 lg:grid-cols-3">
              {d.suggestions.map((s) => (
                <div key={s.title} className="flex flex-col rounded-md border border-line p-3">
                  <div className="text-sm font-semibold">{s.title}</div>
                  <div className="tnum mt-1 text-xs text-muted">{s.basis}</div>
                  <ul className="mt-2 flex-1 space-y-1">
                    {s.evidence.map((e) => (
                      <li key={e.id} className="text-xs">
                        <button type="button" className="text-left text-ink hover:text-teal" onClick={() => nav(`/explorer?conversation=${e.conversation_key}&message=${e.message_id}`)}>
                          “{e.quote.slice(0, 110)}” <ExternalLink className="inline h-3 w-3" aria-label="open message" />
                        </button>
                      </li>
                    ))}
                  </ul>
                  <Button size="sm" variant="ghost" className="mt-2 self-start" disabled={busy} onClick={() => ask(s.question, s.filters)}>Ask Flo <ArrowRight className="h-3.5 w-3.5" aria-hidden /></Button>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-5 xl:grid-cols-2">
            <ChartCard title="Most common primary topics" scope={scope} units={`conversations (denominator ${fmtInt(d.topics.denominator)}; unknown ${fmtInt(d.topics.unknown)})`}
              table={{ head: ["Topic", "Conversations", "Share of scope"], rows: d.topics.items.map((i) => [i.label, i.count, fmtPct(i.share)]) }}
              askQuestion="What are the most common issues in this scope?" filterActive={!!filters.topics?.length} onReset={() => setFilters({ ...filters, topics: [] })}
              footnote={<>Click a bar to filter every chart. <button type="button" className="text-teal underline" onClick={() => openExplorer(filters)}>Inspect matching conversations</button>.</>}>
              <TopicBar data={d.topics} onSelect={toggleTopic} selected={filters.topics} />
            </ChartCard>

            <ChartCard title="Resolution status by topic" scope={scope} units="conversations; stacked by outcome label"
              empty={xt.data && !xt.data.rows.length ? "No conversations in scope." : null}
              table={{ head: ["Topic", ...(xt.data?.columns.map((c) => c.label) ?? []), "Total"], rows: xt.data?.rows.map((r) => [r.label, ...r.cells.map((c) => c.count), r.total]) ?? [] }}
              askQuestion="Compare resolved and unresolved conversations." filterActive={!!filters.resolution?.length} onReset={() => setFilters({ ...filters, resolution: [] })}
              footnote="Click a segment to open those conversations in the explorer.">
              {xt.data ? <ResolutionStacked data={xt.data} onSelect={(t, r) => openExplorer({ ...filters, topics: [t], resolution: [r] })} /> : <Spinner />}
            </ChartCard>

            <ChartCard title="Topic vs inferred ending sentiment" scope={scope} units="conversations (row share)"
              table={{ head: ["Topic", ...(hm.data?.columns.map((c) => c.label) ?? []), "Total"], rows: hm.data?.rows.map((r) => [r.label, ...r.cells.map((c) => c.count), r.total]) ?? [] }}
              askQuestion="Which topics end with negative inferred sentiment, and what do customers say?" filterActive={!!filters.sentiment_end?.length}
              onReset={() => setFilters({ ...filters, sentiment_end: [] })}>
              {hm.data ? <TopicSentimentHeatmap data={hm.data} onSelect={(t, s) => openExplorer({ ...filters, topics: [t], sentiment_end: [s] })} /> : <Spinner />}
            </ChartCard>

            <ChartCard title="Sampled conversation starts by week" scope={scope} units={`conversations started per ISO week${ts.data?.unknown_timestamp ? `; ${ts.data.unknown_timestamp} with unknown timestamp` : ""}`}
              empty={ts.data && ts.data.points.length < 2 ? "Fewer than two valid weeks in scope; a time series is not meaningful." : null}
              table={{ head: ["Week", "Conversations"], rows: ts.data?.points.map((p: any) => [p.bucket, p.total]) ?? [] }}
              askQuestion="How is conversation volume distributed over time in this sample?" footnote={ts.data?.caveat}>
              {ts.data ? <VolumeSeries points={ts.data.points} /> : <Spinner />}
            </ChartCard>

            <ChartCard title="Resolved vs unresolved: cohort comparison" scope={scope} units="share of each cohort with a known value"
              empty={co.data && co.data.segments.some((s: any) => !s.n) ? "One cohort has no conversations in this scope." : null}
              table={{ head: ["Characteristic", ...(co.data?.segments.map((s: any) => `${s.label} (n=${s.n})`) ?? [])], rows: co.data ? [
                ["Negative at start", ...co.data.segments.map((s: any) => s.n ? `${s.negative_start.numerator} of ${s.negative_start.denominator}` : "–")],
                ["Requested escalation", ...co.data.segments.map((s: any) => s.n ? `${s.escalation_requested.numerator} of ${s.escalation_requested.denominator}` : "–")],
                ["Mean messages", ...co.data.segments.map((s: any) => s.mean_messages ?? "–")],
                ["Mean customer turns", ...co.data.segments.map((s: any) => s.mean_customer_turns ?? "–")],
                ["Median first response (min)", ...co.data.segments.map((s: any) => s.median_first_response_min ?? "–")],
              ] : [] }}
              askQuestion="Compare resolved and unresolved conversations." footnote={co.data?.caveat}>
              {co.data ? <CohortComparison segments={co.data.segments} /> : <Spinner />}
            </ChartCard>

            <Card title="Data-quality limitations" subtitle="What these figures can and cannot show">
              <ul className="space-y-1.5 text-sm">
                <li><span className="tnum font-medium">{fmtInt(d.limitations.sampling?.selected)}</span> of <span className="tnum">{fmtInt(d.limitations.sampling?.eligible)}</span> eligible threads selected (seed {d.limitations.sampling?.seed}); requested up to {fmtInt(d.limitations.sampling?.requested)}.</li>
                <li>Unknown labels in scope: topic {d.limitations.unknown_labels.primary_topic}, outcome {d.limitations.unknown_labels.resolution_status}, ending sentiment {d.limitations.unknown_labels.sentiment_end}, escalation {d.limitations.unknown_labels.escalation_requested} (dataset-wide, of {d.limitations.unknown_labels.denominator}).</li>
                <li>Excluded threads: {Object.entries(d.limitations.exclusions).map(([k, v]) => `${k.replace(/_/g, " ")} ${v}`).join(" · ")}</li>
                <li>Sentiment and outcomes are inferred from public replies; many threads continue privately, so outcomes are often unknown.</li>
                <li>No CSAT, revenue, churn or location data exist in this source.</li>
              </ul>
              <Button size="sm" variant="ghost" className="mt-2" onClick={() => nav("/quality")}>Open data quality <ArrowRight className="h-3.5 w-3.5" aria-hidden /></Button>
            </Card>
          </div>
          <Card title="Inferred ending sentiment and escalation" subtitle={`Scope: ${scope}`}>
            <Table head={["Measure", "Category", "Conversations", "Share of scope"]}
              rows={[...d.sentiment.items.map((i) => ["Ending sentiment (inferred)", <span key={i.key}>{i.label}{i.key === "unknown" && <Badge>unknown</Badge>}</span>, i.count, fmtPct(i.share)]),
                ...d.escalation.items.map((i) => ["Escalation request", i.label, i.count, fmtPct(i.share)])]} />
          </Card>
        </>
      )}
    </div>
  );
}
