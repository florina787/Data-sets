import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Crown, HeartHandshake, History, LineChart, MessageSquareText, RotateCw, Sparkles, TrendingDown } from "lucide-react";
import { useEffect, useRef } from "react";
import { useApp, type Turn } from "@/app/AppState";
import { Composer } from "@/components/chat/Composer";
import { ProgressStages } from "@/components/chat/ProgressStages";
import { ResponseView } from "@/components/chat/ResponseView";
import { Badge, Button, ErrorState, Skeleton } from "@/components/common/ui";
import { useAsync } from "@/hooks/useAsync";
import { num, pct, timeAgo } from "@/lib/format";
import { api } from "@/services/api";

const ASSIGNMENT = [
  { icon: TrendingDown, tag: "Sentiment × topics", q: "What were the top 5 topics most associated with negative customer sentiment in the last month represented in the dataset?" },
  { icon: HeartHandshake, tag: "Agent coaching", q: "Which support agents may benefit from additional coaching on empathy or customer communication, and what evidence supports that view?" },
  { icon: LineChart, tag: "Conversation journey", q: "How did customer sentiment change over the course of a selected conversation?" },
  { icon: Crown, tag: "Leadership priorities", q: "Which recurring customer concerns should contact-centre leadership review first?" },
];
const MORE = [
  "Show the sentiment trend over time.",
  "Which products have the highest negative rate?",
  "Does the agent's closing action fit the customer's issue, by topic?",
  "Find conversations where the customer asked to escalate an app crash.",
  "How did customer sentiment change in conversation C0000479?",
  "What does the dataset cover?",
];

function Hero() {
  const { ask, sessionId, loadSession } = useApp();
  const overview = useAsync(() => api.analytics("dataset_overview"), []);
  const sessions = useAsync(() => api.get<any[]>("/api/sessions?limit=5"), []);
  const m = (id: string) => overview.data?.metrics.find((x) => x.id === id)?.value;
  return (
    <div className="mx-auto max-w-4xl pt-4 sm:pt-10">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="text-center">
        <Badge tone="indigo" className="mb-4"><Sparkles className="h-3 w-3" />Agentic analysis · evidence-backed · explainable</Badge>
        <h1 className="bg-gradient-to-br from-white via-white to-slate-400 bg-clip-text text-3xl font-semibold tracking-tight text-transparent sm:text-5xl">
          What should we understand about our customers?
        </h1>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-muted sm:text-base">
          Ask in plain language. A supervised team of agents queries the conversations, verifies the numbers, retrieves source evidence and explains what it found — and how sure it is.
        </p>
      </motion.div>
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1 }} className="mt-8">
        <Composer large autoFocus />
      </motion.div>
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {ASSIGNMENT.map(({ icon: Icon, tag, q }, i) => (
          <motion.button key={q} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.05 }} onClick={() => ask(q)}
            className="focus-ring group flex gap-3 rounded-2xl border border-line bg-surface/60 p-4 text-left transition hover:border-indigo/40 hover:bg-elevated/60">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo/25 to-cyan/10 text-cyan ring-1 ring-line"><Icon className="h-4 w-4" /></div>
            <div className="min-w-0">
              <p className="label">{tag}</p>
              <p className="mt-1 text-sm leading-snug text-ink/90">{q}</p>
            </div>
            <ArrowRight className="ml-auto mt-1 h-4 w-4 shrink-0 text-faint opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
          </motion.button>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {MORE.map((q) => (
          <button key={q} onClick={() => ask(q)} className="focus-ring rounded-full border border-line bg-white/[0.02] px-3 py-1.5 text-xs text-muted transition hover:border-indigo/40 hover:text-ink">{q}</button>
        ))}
      </div>
      <div className="mt-10 grid gap-4 md:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-line bg-surface/50 p-4">
          <p className="label mb-3">Dataset in scope</p>
          {overview.loading ? <Skeleton className="h-16" /> : overview.error ? <ErrorState message={overview.error.message} onRetry={overview.reload} /> : (
            <div className="grid grid-cols-3 gap-3 text-center">
              {[["Conversations", num(m("conversations_in_scope") as number)], ["Messages", num(m("messages") as number)], ["Negative", pct(m("negative_rate_overall") as number)],
                ["Topics", m("topics")], ["Products", m("products")], ["Labelled", pct(m("label_coverage") as number, 0)]].map(([k, v]) => (
                <div key={k as string}><p className="num text-lg font-semibold">{v as any}</p><p className="text-[11px] text-faint">{k}</p></div>
              ))}
              <p className="col-span-3 text-[11px] text-faint">Syncora.ai customer-support sample · {String(m("date_range") ?? "")}</p>
            </div>
          )}
        </div>
        <div className="rounded-2xl border border-line bg-surface/50 p-4">
          <p className="label mb-3 flex items-center gap-1.5"><History className="h-3 w-3" />Recent sessions</p>
          {sessions.loading ? <Skeleton className="h-16" /> : !sessions.data?.length ? <p className="text-xs text-faint">No sessions yet.</p> : (
            <ul className="space-y-1">
              {sessions.data.filter((s) => s.session_id !== sessionId).slice(0, 4).map((s) => (
                <li key={s.session_id}>
                  <button onClick={() => loadSession(s.session_id)} className="focus-ring flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs hover:bg-white/[0.04]">
                    <MessageSquareText className="h-3.5 w-3.5 shrink-0 text-faint" />
                    <span className="min-w-0 flex-1 truncate text-ink/85">{s.title}</span>
                    <span className="shrink-0 text-faint">{s.turns} · {timeAgo(s.updated_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function TurnView({ t, last }: { t: Turn; last: boolean }) {
  const { retry } = useApp();
  return (
    <motion.article initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="space-y-4" aria-label={`Question: ${t.question}`}>
      <div className="flex justify-end">
        <div className="max-w-2xl rounded-2xl rounded-tr-md border border-indigo/30 bg-gradient-to-br from-indigo/20 to-violet/10 px-4 py-2.5 text-sm text-ink">{t.question}</div>
      </div>
      <div className="rounded-2xl border border-line bg-surface/60 p-4 sm:p-6">
        {t.order.length > 0 && <div className="mb-5"><ProgressStages turn={t} compact={t.status === "done"} /></div>}
        {t.status === "streaming" && !t.response && (
          <div className="space-y-3"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-5/6" />
            <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-20" />)}</div></div>
        )}
        {t.status === "error" && <ErrorState message={t.error ?? "The analysis failed."} onRetry={t.retryable ? () => retry(t.id) : undefined} />}
        {t.status === "cancelled" && (
          <div className="flex items-center justify-between gap-3 text-sm text-muted">Analysis stopped.<Button size="sm" variant="outline" onClick={() => retry(t.id)}><RotateCw className="h-3.5 w-3.5" />Run again</Button></div>
        )}
        {t.response && <ResponseView r={t.response} />}
      </div>
      {last && <div className="h-2" />}
    </motion.article>
  );
}

export default function AskIntelligence() {
  const { turns } = useApp();
  const endRef = useRef<HTMLDivElement>(null);
  const count = turns.length;
  useEffect(() => { if (count) endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [count]);
  if (!turns.length) return <Hero />;
  return (
    <div className="mx-auto flex max-w-6xl flex-col">
      <div className="flex-1 space-y-8 pb-36">
        <AnimatePresence initial={false}>{turns.map((t, i) => <TurnView key={t.id} t={t} last={i === turns.length - 1} />)}</AnimatePresence>
        <div ref={endRef} />
      </div>
      <div className="sticky bottom-0 -mx-2 bg-gradient-to-t from-bg via-bg/95 to-transparent px-2 pb-4 pt-6">
        <Composer />
        <p className="mt-2 text-center text-[11px] text-faint">Follow-ups keep context (“compare the top two”, “previous month”, “the first one”). Numbers are computed, not generated.</p>
      </div>
    </div>
  );
}
