import { api, dsPath } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { fmtInt, fmtPct } from "../lib/format";
import { Badge, Card, ErrorBox, Notice, PageHeader, Spinner, Stat, Table } from "../components/ui";
import { ChartCard } from "../charts/ChartCard";
import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export function Languages() {
  const { dataset } = useApp();
  const q = useData<any>((id) => api(dsPath(id, "languages")));
  const d = q.data;
  if (!dataset) return <PageHeader title="Language intelligence" />;
  return (
    <div className="space-y-4">
      <PageHeader title="Language intelligence" description="Message-level language labels, coverage of analytical labels by language, reviewed quality and guarded comparisons." />
      {q.error && <ErrorBox onRetry={q.reload}>{q.error}</ErrorBox>}
      {!d ? <Spinner /> : (
        <>
          <Notice>{d.notes[0]}</Notice>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <Stat label="Messages" value={fmtInt(d.total_messages)} />
            <Stat label="Unknown language" value={fmtInt(d.unknown_messages)} sub={fmtPct(d.unknown_messages / (d.total_messages || 1))} />
            <Stat label="Mixed-language messages" value={fmtInt(d.mixed_messages)} />
            <Stat label="Conversations with >1 language" value={fmtInt(d.conversations_with_multiple_languages)} />
            <Stat label="Reviewer-corrected labels" value={fmtInt(d.reviewer_corrected_messages)} />
          </div>
          <ChartCard title="Messages by detected language" scope={dataset.name} units={`messages (denominator ${fmtInt(d.total_messages)}); unknown and mixed shown`}
            table={{ head: ["Language", "Messages", "Customer", "Support"], rows: d.messages_by_language.map((r: any) => [r.language, r.messages, r.customer, r.support]) }}
            askQuestion="How do outcomes differ by message language, and is the comparison valid?">
            <ResponsiveContainer width="100%" height={Math.max(160, d.messages_by_language.length * 30)}>
              <BarChart data={d.messages_by_language} layout="vertical" margin={{ left: 8, right: 48 }}>
                <CartesianGrid horizontal={false} stroke="#EEF1F5" />
                <XAxis type="number" domain={[0, "auto"]} allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="language" width={70} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: any) => [fmtInt(v), "messages"]} />
                <Bar dataKey="messages" fill="#087F8C" isAnimationActive={false}><LabelList dataKey="messages" position="right" style={{ fontSize: 11 }} /></Bar>
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
          <Card title="Groups by language of the first customer message" subtitle={`Outcome rates appear only when a group has at least ${d.min_group_size} conversations with known outcomes. Topic mix is shown because it can explain differences.`}>
            <Table head={["Language", "Conversations", "Topic label coverage", "Outcome label coverage", "Sentiment coverage", "Explicitly unresolved", "Top topics"]}
              rows={d.groups.map((g: any) => [g.language, g.conversations,
                `${g.coverage.topic.known} of ${g.coverage.topic.n}`, `${g.coverage.resolution.known} of ${g.coverage.resolution.n}`, `${g.coverage.sentiment_end.known} of ${g.coverage.sentiment_end.n}`,
                g.comparison_allowed ? `${g.explicitly_unresolved.numerator} of ${g.explicitly_unresolved.denominator} (${fmtPct(g.explicitly_unresolved.numerator / g.explicitly_unresolved.denominator)})` : <span key="s" className="text-xs text-muted">{g.suppressed_reason}</span>,
                g.topic_mix.map((t: any) => `${t.label} ${t.count}`).join(", ")])} />
          </Card>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Reviewed quality by language" subtitle="Latest evaluation per suite and language; small samples are marked. Languages without reference data are unevaluated.">
              {!d.reviewed_quality.length ? <p className="text-sm text-muted">No evaluations have been run. Run them on Observability and evaluation.</p> : (
                <Table head={["Suite", "Language", "System", "n", "Score"]} rows={d.reviewed_quality.sort((a: any, b: any) => a.suite.localeCompare(b.suite) || a.language.localeCompare(b.language))
                  .map((r: any) => [r.suite.replace(/_/g, " "), r.language, r.system, r.n, <span key="s">{fmtPct(r.score)}{r.n < 5 && <Badge>small n</Badge>}</span>])} />
              )}
            </Card>
            <Card title="Translations" subtitle="Stored separately from the original text, which remains the authoritative evidence">
              {!d.translations.length ? <p className="text-sm text-muted">No translations stored for this dataset.</p> : (
                <Table head={["Method", "Needs bilingual review", "Count"]} rows={d.translations.map((t: any) => [t.method, t.needs_review ? "yes" : "no", t.count])} />
              )}
              <ul className="mt-2 list-disc pl-5 text-xs text-muted">{d.notes.slice(1).map((n: string) => <li key={n}>{n}</li>)}<li>Translation checks: numbers, currency, dates, negation, identifiers and approved terminology.</li></ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
