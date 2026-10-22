import { ChevronLeft, ChevronRight, MessagesSquare, Search, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { Badge, Button, Card, EmptyState, ErrorState, PageHeader, SentimentBadge, Skeleton, Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/common/ui";
import { TranscriptViewer } from "@/components/evidence/TranscriptViewer";
import { useAsync } from "@/hooks/useAsync";
import { score } from "@/lib/format";
import { cn } from "@/lib/utils";
import { api } from "@/services/api";

interface ListResp { total: number; page: number; page_size: number; items: Record<string, any>[] }
interface Tax { topics: { id: string; label: string }[]; months: string[]; products: { product: string }[] }

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-faint">{label}
      <select value={value} onChange={(e) => onChange(e.target.value)} className="focus-ring rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink">
        <option value="">All</option>{options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

function SemanticSearch({ onOpen }: { onOpen: (id: string) => void }) {
  const { datasetMode } = useApp();
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    if (q.trim().length < 2) return;
    setBusy(true); setErr(null);
    try { setRes(await api.post("/api/retrieval/search", { query: q, k: 10, dataset_mode: datasetMode })); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-3">
      <form onSubmit={(e) => { e.preventDefault(); run(); }} className="flex gap-2">
        <label htmlFor="sem" className="sr-only">Semantic search</label>
        <input id="sem" value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. customer charged twice for wallet, wants escalation"
          className="focus-ring flex-1 rounded-xl border border-line bg-surface px-3 py-2 text-sm placeholder:text-faint" />
        <Button variant="primary" disabled={busy}><Sparkles className="h-4 w-4" />Search</Button>
      </form>
      {err && <ErrorState message={err} />}
      {res && (
        <>
          <p className="text-[11px] text-faint">{res.results.length} passages · {res.latency_ms} ms · {res.embedding_backend} · {res.score_note}</p>
          <ul className="space-y-2">
            {res.results.map((r: any) => (
              <li key={r.evidence_id}>
                <button onClick={() => onOpen(r.conversation_id)} className="focus-ring w-full rounded-xl border border-line bg-white/[0.02] p-3 text-left hover:border-indigo/40">
                  <div className="flex flex-wrap items-center gap-1.5 text-xs"><span className="font-mono text-cyan">{r.conversation_id}</span><Badge>{r.topic}</Badge>
                    {r.product && <Badge>{r.product}</Badge>}<SentimentBadge value={r.sentiment} /><Badge tone="cyan">sim {r.similarity.toFixed(2)}</Badge>
                    <span className="text-faint">turns {r.turn_range[0]}–{r.turn_range[1]}</span></div>
                  <pre className="mt-2 whitespace-pre-wrap font-sans text-xs leading-relaxed text-ink/80">{r.text}</pre>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

export default function Explorer() {
  const { conversationId } = useParams();
  const nav = useNavigate();
  const { datasetMode, setSelectedConversation } = useApp();
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [topic, setTopic] = useState("");
  const [sentiment, setSentiment] = useState("");
  const [month, setMonth] = useState("");
  const [sort, setSort] = useState("id");
  const [page, setPage] = useState(1);
  useEffect(() => { const t = setTimeout(() => setDebounced(q), 300); return () => clearTimeout(t); }, [q]);
  useEffect(() => setPage(1), [debounced, topic, sentiment, month, sort]);
  useEffect(() => { if (conversationId) setSelectedConversation(conversationId); }, [conversationId, setSelectedConversation]);
  const tax = useAsync(() => api.get<Tax>("/api/analytics/taxonomy"), []);
  const params = new URLSearchParams({ page: String(page), page_size: "20", sort, dataset_mode: datasetMode });
  if (debounced) params.set("q", debounced);
  if (topic) params.set("topic", topic);
  if (sentiment) params.set("sentiment", sentiment);
  if (month) params.set("month", month);
  const list = useAsync(() => api.get<ListResp>(`/api/conversations?${params}`), [params.toString()]);
  const open = (id: string) => nav(`/explorer/${id}`);
  const pages = list.data ? Math.max(1, Math.ceil(list.data.total / list.data.page_size)) : 1;
  return (
    <div className="mx-auto max-w-[1500px]">
      <PageHeader title="Conversation Explorer" icon={<MessagesSquare className="h-5 w-5" />} subtitle="Search, filter and inspect every source conversation, with labels and source line references." />
      <div className="grid gap-5 lg:grid-cols-[440px_1fr]">
        <Card className="p-4">
          <Tabs defaultValue="browse">
            <TabsList className="mb-3"><TabsTrigger value="browse">Browse</TabsTrigger><TabsTrigger value="semantic">Semantic search</TabsTrigger></TabsList>
            <TabsContent value="browse" className="space-y-3">
              <div className="relative">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-faint" aria-hidden />
                <label htmlFor="q" className="sr-only">Search conversations</label>
                <input id="q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="ID, agent or text…" className="focus-ring w-full rounded-xl border border-line bg-surface py-2 pl-9 pr-3 text-sm placeholder:text-faint" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Select label="Topic" value={topic} onChange={setTopic} options={(tax.data?.topics ?? []).filter((t) => t.id !== "other").map((t) => [t.id, t.label])} />
                <Select label="Sentiment" value={sentiment} onChange={setSentiment} options={["negative", "mixed", "neutral", "positive"].map((s) => [s, s])} />
                <Select label="Start month" value={month} onChange={setMonth} options={(tax.data?.months ?? []).map((m) => [m, m])} />
                <label className="flex flex-col gap-1 text-[11px] text-faint">Sort
                  <select value={sort} onChange={(e) => setSort(e.target.value)} className="focus-ring rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink">
                    <option value="id">ID</option><option value="date">Newest</option><option value="most_negative">Most negative</option><option value="most_positive">Most positive</option>
                  </select></label>
              </div>
              {list.error ? <ErrorState message={list.error.message} onRetry={list.reload} /> : list.loading && !list.data ? (
                <div className="space-y-2">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-12" />)}</div>
              ) : !list.data?.items.length ? <EmptyState title="No conversations match" description="Clear a filter or try another search." /> : (
                <>
                  <p className="text-[11px] text-faint">{list.data.total.toLocaleString()} conversations</p>
                  <ul className={cn("divide-y divide-line overflow-hidden rounded-xl border border-line", list.loading && "opacity-60")}>
                    {list.data.items.map((c) => (
                      <li key={c.conversation_id}>
                        <button onClick={() => open(c.conversation_id)} aria-current={c.conversation_id === conversationId}
                          className={cn("focus-ring w-full px-3 py-2.5 text-left transition hover:bg-white/[0.03]", c.conversation_id === conversationId && "bg-indigo/10")}>
                          <div className="flex items-center gap-2 text-xs"><span className="font-mono text-cyan">{c.conversation_id}</span><span className="text-faint">{String(c.start_timestamp).slice(0, 10)}</span>
                            <span className="ml-auto"><SentimentBadge value={c.sentiment} /></span></div>
                          <p className="mt-0.5 truncate text-xs text-muted">{c.topic_label} · {c.product ?? "—"} · {c.agent_id} · mean {score(c.mean_sentiment)}</p>
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center justify-between text-xs text-muted">
                    <Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
                    <span>Page {page} of {pages}</span>
                    <Button size="sm" variant="ghost" disabled={page >= pages} onClick={() => setPage((p) => p + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
                  </div>
                </>
              )}
            </TabsContent>
            <TabsContent value="semantic"><SemanticSearch onOpen={open} /></TabsContent>
          </Tabs>
        </Card>
        <Card className="min-h-[60vh] p-5">
          {conversationId ? <TranscriptViewer conversationId={conversationId} /> : (
            <EmptyState title="Select a conversation" description="Pick a conversation to see its transcript, turn-by-turn sentiment and source references. Selecting one also makes it the target for conversation questions in Ask Intelligence." />
          )}
        </Card>
      </div>
    </div>
  );
}
