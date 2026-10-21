import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { GitBranch, CornerDownRight, Download } from "lucide-react";
import { api, dsPath, filtersParam, type Filters } from "../lib/api";
import { useApp, useData } from "../lib/state";
import { fmtDate, fmtInt } from "../lib/format";
import { ESCALATION_LABELS, RESOLUTION_LABELS, SENTIMENT_LABELS, TOPIC_LABELS } from "../lib/palette";
import { Badge, Button, Card, Empty, ErrorBox, Field, PageHeader, Spinner, inputCls } from "../components/ui";
import { ChartCard } from "../charts/ChartCard";
import { SentimentJourney } from "../charts/charts";

const SELECTS: { key: keyof Filters; label: string; options: Record<string, string> }[] = [
  { key: "topics", label: "Topic", options: TOPIC_LABELS },
  { key: "resolution", label: "Outcome", options: RESOLUTION_LABELS },
  { key: "sentiment_end", label: "Ending sentiment", options: SENTIMENT_LABELS },
  { key: "escalation", label: "Escalation", options: ESCALATION_LABELS },
];

export function FilterBar() {
  const { filters, setFilters } = useApp();
  return (
    <div className="flex flex-wrap items-end gap-3">
      {SELECTS.map((s) => (
        <Field key={s.key} label={s.label}>
          <select className={inputCls} value={(filters[s.key] as string[] | undefined)?.[0] ?? ""}
            onChange={(e) => setFilters({ ...filters, [s.key]: e.target.value ? [e.target.value] : [] })}>
            <option value="">All</option>
            {Object.entries(s.options).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </Field>
      ))}
      <Field label="Message language">
        <input className={`${inputCls} w-24`} placeholder="e.g. es" value={filters.languages?.[0] ?? ""}
          onChange={(e) => setFilters({ ...filters, languages: e.target.value.trim() ? [e.target.value.trim()] : [] })} />
      </Field>
      <Field label="From"><input type="date" className={inputCls} value={filters.date_from ?? ""} onChange={(e) => setFilters({ ...filters, date_from: e.target.value || undefined })} /></Field>
      <Field label="To"><input type="date" className={inputCls} value={filters.date_to ?? ""} onChange={(e) => setFilters({ ...filters, date_to: e.target.value || undefined })} /></Field>
      <Button size="sm" onClick={() => setFilters({})}>Reset</Button>
    </div>
  );
}

function Highlighted({ text, spans, focus }: { text: string; spans: { start: number; end: number; supports: string }[]; focus?: { start: number; end: number } | null }) {
  const all = [...spans, ...(focus ? [{ ...focus, supports: "cited" }] : [])].filter((s) => s.start != null && s.end != null).sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let pos = 0;
  all.forEach((s, i) => {
    if (s.start < pos) return; // overlapping spans: keep first
    if (s.start > pos) parts.push(text.slice(pos, s.start));
    parts.push(<mark key={i} title={`Evidence for ${s.supports}`} className={`rounded px-0.5 ${s.supports === "cited" ? "bg-[#ffe6a8]" : "bg-teal-light"} text-ink underline decoration-teal decoration-dotted`}>{text.slice(s.start, s.end)}</mark>);
    pos = s.end;
  });
  if (pos < text.length) parts.push(text.slice(pos));
  return <>{parts}</>;
}

function ConversationDetail({ datasetId, convKey, messageId, span }: { datasetId: string; convKey: string; messageId: string | null; span: { start: number; end: number } | null }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const load = () => api<any>(dsPath(datasetId, `conversations/${convKey}`)).then(setD).catch((e) => setErr(e.message));
  useEffect(() => { setD(null); load(); }, [datasetId, convKey]);
  useEffect(() => {
    if (d && messageId) document.getElementById(`msg-${messageId}`)?.scrollIntoView({ block: "center" });
  }, [d, messageId]);
  const tree = useMemo(() => {
    if (!d) return [];
    const kids: Record<string, any[]> = {};
    const ids = new Set(d.messages.map((m: any) => m.message_id));
    const roots: any[] = [];
    for (const m of d.messages) {
      if (m.parent_id && ids.has(m.parent_id)) (kids[m.parent_id] ??= []).push(m); else roots.push(m);
    }
    const out: { m: any; depth: number; branch: boolean; siblings: number }[] = [];
    const walk = (m: any, depth: number, siblings: number) => {
      out.push({ m, depth, branch: (kids[m.message_id]?.length ?? 0) > 1, siblings });
      (kids[m.message_id] ?? []).forEach((c) => walk(c, depth + 1, kids[m.message_id].length));
    };
    roots.forEach((r) => walk(r, 0, roots.length));
    return out;
  }, [d]);
  if (err) return <ErrorBox>{err}</ErrorBox>;
  if (!d) return <Spinner />;
  const ev = (d.analysis?.evidence ?? []) as any[];
  const correct = async (field: string, value: string) => {
    if (!reviewer) { setMsg("Enter your name as reviewer first."); return; }
    try {
      const r = await api<any>(dsPath(datasetId, `conversations/${convKey}/corrections`), { body: { field, value, reviewer } });
      setMsg(r.confirmed_unchanged ? `Confirmed ${field} (recorded as a review).` : `Corrected ${field}. Original prediction preserved.`);
      load();
    } catch (e: any) { setMsg(e.message); }
  };
  const correctLang = async (message_id: string, language: string) => {
    if (!reviewer) { setMsg("Enter your name as reviewer first."); return; }
    try { await api(dsPath(datasetId, "messages/language"), { body: { message_id, language, reviewer } }); setMsg("Language label corrected."); load(); }
    catch (e: any) { setMsg(e.message); }
  };
  const labelRows: [string, string, Record<string, string>][] = [
    ["primary_topic", "Primary topic", TOPIC_LABELS], ["resolution_status", "Outcome", RESOLUTION_LABELS],
    ["sentiment_start", "Starting sentiment", SENTIMENT_LABELS], ["sentiment_end", "Ending sentiment", SENTIMENT_LABELS],
    ["escalation_requested", "Escalation requested", ESCALATION_LABELS],
  ];
  return (
    <div className="space-y-4">
      <Card title={<span className="font-mono text-sm">{d.conversation_key}</span>}
        subtitle={`${d.brand ?? "unknown account"} · ${d.message_count} messages · ${d.branch_count} branch point(s) · max depth ${d.max_depth} · started ${fmtDate(d.started_at, { dateStyle: "medium", timeStyle: "short" } as any)} · first response ${d.first_response_min ?? "–"} min · ${d.completeness}`}>
        <ol className="space-y-2" aria-label="Conversation messages in reply order">
          {tree.map(({ m, depth, branch }) => {
            const spans = ev.filter((e) => e.message_id === m.message_id);
            const focused = messageId === m.message_id;
            return (
              <li key={m.message_id} id={`msg-${m.message_id}`} style={{ marginLeft: Math.min(depth, 6) * 20 }}
                className={`rounded-md border px-3 py-2 ${m.role === "customer" ? "border-line bg-white" : "border-[#bfe0e2] bg-teal-light/40"} ${focused ? "ring-2 ring-amber" : ""}`}>
                <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                  {depth > 0 && <CornerDownRight className="h-3 w-3" aria-label={`reply to ${m.parent_id}`} />}
                  <Badge tone={m.role === "customer" ? "neutral" : "teal"}>{m.role === "customer" ? "Customer" : "Support"}</Badge>
                  <span className="font-mono">#{m.message_id}</span>
                  {m.parent_id && <span>reply to #{m.parent_id}</span>}
                  <span>{fmtDate(m.created_at, { dateStyle: "short", timeStyle: "short" } as any)}</span>
                  <Badge title="Message-level language label">lang: {m.language}{m.language_corrected ? " (reviewed)" : ""}</Badge>
                  {m.stage && <Badge title="Inferred journey stage (rules)">{m.stage.replace("_", " ")}</Badge>}
                  {branch && <Badge tone="amber"><GitBranch className="h-3 w-3" aria-hidden />branch: {m.replies} replies</Badge>}
                  {focused && <Badge tone="amber">Cited message</Badge>}
                </div>
                <p className="whitespace-pre-wrap text-sm text-ink"><Highlighted text={m.text} spans={spans} focus={focused ? span : null} /></p>
                {m.translations?.map((t: any, i: number) => (
                  <div key={i} className="mt-1.5 rounded border border-[#ecd3ad] bg-amber-light/50 px-2 py-1 text-xs">
                    <Badge tone="amber">Translated quotation · {t.method}{t.model_id ? ` · ${t.model_id}` : ""} · {t.prompt_version}</Badge>{t.needs_review && <Badge tone="red">needs bilingual review</Badge>}
                    <div className="mt-0.5 text-ink">{t.text}</div>
                  </div>
                ))}
                <details className="mt-1 text-[11px] text-muted">
                  <summary className="cursor-pointer">Correct language label</summary>
                  <div className="mt-1 flex gap-1">
                    {["en", "es", "fr", "de", "pt", "hi-Latn", "mixed", "unknown"].map((l) => (
                      <button key={l} type="button" className="rounded border border-line px-1.5 hover:border-teal" onClick={() => correctLang(m.message_id, l)}>{l}</button>
                    ))}
                  </div>
                </details>
              </li>
            );
          })}
        </ol>
        <p className="mt-2 text-[11px] text-muted">Text is redacted at import (handles, emails, phones, cards, IDs, URLs, some names). Highlights mark evidence spans validated against this stored text.</p>
      </Card>

      <Card title="Extracted labels" subtitle={d.analysis ? `Method: ${d.analysis.method}${d.analysis.model_id ? ` · ${d.analysis.model_id}` : ""} · ${d.analysis.prompt_version}${d.labels.corrected ? " · includes reviewer corrections" : ""}` : "No analysis"}>
        <Field label="Reviewer name (required to confirm or correct)"><input className={inputCls} value={reviewer} onChange={(e) => setReviewer(e.target.value)} /></Field>
        <table className="mt-3 w-full text-sm">
          <tbody>
            {labelRows.map(([field, label, opts]) => (
              <tr key={field} className="border-t border-line">
                <th scope="row" className="py-1.5 pr-2 text-left text-xs font-medium text-muted">{label}</th>
                <td className="py-1.5">{opts[d.labels[field]] ?? d.labels[field]}</td>
                <td className="py-1.5 text-right">
                  <select aria-label={`Correct ${label}`} className={`${inputCls} py-0.5 text-xs`} value="" onChange={(e) => e.target.value && correct(field, e.target.value)}>
                    <option value="">Confirm / correct…</option>
                    {Object.entries(opts).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {msg && <p className="mt-2 text-xs text-teal" role="status">{msg}</p>}
        {d.analysis && (
          <div className="mt-3 space-y-1 text-xs">
            <div><Badge>Inference</Badge> {d.analysis.summary}</div>
            {d.analysis.claims?.map((c: any, i: number) => <div key={i}><Badge tone={c.kind === "observed" ? "green" : c.kind === "hypothesis" ? "amber" : "neutral"}>{c.kind}</Badge> {c.text}</div>)}
            {d.analysis.invalid_evidence?.length > 0 && <div className="text-red">{d.analysis.invalid_evidence.length} evidence span(s) failed validation and were dropped.</div>}
          </div>
        )}
        {d.corrections.length > 0 && (
          <div className="mt-3 text-xs">
            <div className="font-medium text-muted">Review history</div>
            <ul className="mt-1 space-y-0.5">{d.corrections.map((c: any, i: number) => <li key={i}>{c.reviewer}: {c.field} {c.original} → {c.corrected} ({fmtDate(c.at)})</li>)}</ul>
          </div>
        )}
      </Card>

      <ChartCard title="Sentiment journey" scope={`conversation ${d.conversation_key}`} units="inferred sentiment per customer turn (rules)"
        empty={d.sentiment_journey.turns.length < 2 ? "Fewer than two customer turns: a journey cannot be shown." : null}
        table={{ head: ["Turn", "Message", "Inferred sentiment", "Supporting text"], rows: d.sentiment_journey.turns.map((t: any) => [t.position, t.message_id, t.sentiment, t.evidence ?? ""]) }}
        askQuestion="Show the evidence behind this chart." footnote={d.sentiment_journey.method}>
        <SentimentJourney turns={d.sentiment_journey.turns} onSelect={(id) => document.getElementById(`msg-${id}`)?.scrollIntoView({ block: "center" })} />
      </ChartCard>
    </div>
  );
}

export function Explorer() {
  const { dataset, filters, setFilters, datasets, setDatasetId, setMode } = useApp();
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const conv = params.get("conversation");
  const msgId = params.get("message");
  // Deep links from Flo citations and charts: dataset, filters, conversation and message.
  useEffect(() => {
    const ds = params.get("dataset");
    if (ds && dataset && ds !== dataset.id) {
      const target = datasets.find((d) => d.id === ds);
      if (target) { setMode(target.synthetic ? "demo" : "connected"); setDatasetId(ds); }
    }
    const f = params.get("filters");
    if (f) { try { setFilters(JSON.parse(f)); } catch { /* ignore */ } params.delete("filters"); setParams(params, { replace: true }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => setPage(1), [JSON.stringify(filters), query]);
  const list = useData<any>((id, f) => api(dsPath(id, "conversations"), { params: { filters: filtersParam(f), q: query || undefined, page, page_size: 20 } }), [query, page]);
  const span = useMemo(() => null, []);
  if (!dataset) return <PageHeader title="Conversation explorer" />;
  return (
    <div className="space-y-4">
      <PageHeader title="Conversation explorer" description="Search and filter conversations; open full redacted threads with reply branches, labels and evidence."
        actions={<a className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-3 py-1.5 text-sm" href={`${dsPath(dataset.id, "conversations/export.csv")}${filtersParam(filters) ? `?filters=${encodeURIComponent(filtersParam(filters)!)}` : ""}`}><Download className="h-3.5 w-3.5" aria-hidden />Export CSV</a>} />
      <Card>
        <FilterBar />
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); setQuery(q); }}>
          <input className={`${inputCls} flex-1`} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search messages (keyword + semantic when available)…" aria-label="Search messages" />
          <Button type="submit" variant="primary">Search</Button>
          {query && <Button onClick={() => { setQ(""); setQuery(""); }}>Clear</Button>}
        </form>
        {list.data?.retrieval && (
          <p className="mt-1 text-[11px] text-muted">Retrieval: {list.data.retrieval.methods_used.join(" + ") || "none"}{list.data.retrieval.semantic_unavailable_reason ? ` · semantic search unavailable (${list.data.retrieval.semantic_unavailable_reason.slice(0, 90)})` : ""}. Search ranks examples; it does not count.</p>
        )}
      </Card>
      <div className="grid gap-4 xl:grid-cols-[minmax(340px,420px)_1fr]">
        <Card title={`${fmtInt(list.data?.total)} conversations`} subtitle={`Scope: ${list.data?.scope ?? ""}${query ? ` · matching “${query}”` : ""}`}>
          {list.error && <ErrorBox onRetry={list.reload}>{list.error}</ErrorBox>}
          {!list.data ? <Spinner /> : !list.data.items.length ? <Empty title="No conversations match">Adjust or reset the filters.</Empty> : (
            <ul className="divide-y divide-line">
              {list.data.items.map((c: any) => (
                <li key={c.key}>
                  <button type="button" onClick={() => { params.set("conversation", c.key); params.delete("message"); setParams(params); }}
                    className={`w-full px-1 py-2 text-left hover:bg-app ${conv === c.key ? "bg-teal-light/60" : ""}`} aria-current={conv === c.key}>
                    <div className="line-clamp-2 text-sm text-ink">{c.matches?.[0]?.text ?? c.first_message}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      <Badge>{TOPIC_LABELS[c.primary_topic] ?? c.primary_topic}</Badge>
                      <Badge tone={c.resolution_status === "unresolved_explicit" ? "red" : c.resolution_status === "resolved_confirmed" ? "green" : "neutral"}>{RESOLUTION_LABELS[c.resolution_status]}</Badge>
                      {c.escalation_requested === "yes" && <Badge tone="amber">Escalation</Badge>}
                      {c.branch_count > 0 && <Badge>branched</Badge>}
                      {c.corrected && <Badge tone="teal">reviewed</Badge>}
                      <span className="text-[11px] text-muted">{c.message_count} msgs · {c.languages.join(", ")}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {list.data && list.data.total > 20 && (
            <div className="mt-2 flex items-center justify-between text-xs text-muted">
              <Button size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
              Page {page} of {Math.ceil(list.data.total / 20)}
              <Button size="sm" disabled={page * 20 >= list.data.total} onClick={() => setPage(page + 1)}>Next</Button>
            </div>
          )}
        </Card>
        <div>{conv ? <ConversationDetail datasetId={dataset.id} convKey={conv} messageId={msgId} span={span} /> : <Empty title="Select a conversation">Open a conversation to see every turn, reply branches, labels and evidence.</Empty>}</div>
      </div>
    </div>
  );
}
