import { motion } from "framer-motion";
import {
  AlertTriangle, BrainCircuit, CalendarDays, CheckCircle2, ChevronDown, CircleHelp, Clock, FileSearch, Lightbulb, Network, Quote, ShieldCheck, Sparkles, UserCheck,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { ChartCard } from "@/components/charts/ChartCard";
import { Badge, Card, CardHeader, SentimentBadge, Tip } from "@/components/common/ui";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { RelationGraph } from "@/components/workflow/RelationGraph";
import { humanize, ms } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChatResponse, Evidence, Recommendation } from "@/types/api";

const FULL_WIDTH = new Set(["timeline", "heatmap", "table"]);

export function EvidenceCard({ e, i }: { e: Evidence; i: number }) {
  const { openConversation } = useEvidence();
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 * i }}
      className="flex h-full flex-col rounded-xl border border-line bg-white/[0.02] p-3.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <button onClick={() => openConversation(e.conversation_id, e.message_ids)} className="focus-ring rounded font-mono text-xs text-cyan hover:underline">{e.conversation_id}</button>
        <Badge>{e.topic}</Badge>
        {e.product && <Badge>{e.product}</Badge>}
        <SentimentBadge value={e.sentiment} />
        {e.similarity !== null && <Tip content="Cosine similarity between the query and passage embeddings: a ranking signal, not a probability."><span><Badge tone="cyan">sim {e.similarity.toFixed(2)}</Badge></span></Tip>}
      </div>
      <p className="mt-1.5 text-[11px] text-faint">{e.reason} · turns {e.turn_range[0]}–{e.turn_range[1]} · {e.agent_id} · {e.date}</p>
      <div className="mt-2 flex-1 space-y-1.5">
        {e.excerpts.slice(0, 4).map((x) => (
          <p key={x.message_id} className="flex gap-2 text-xs leading-relaxed">
            <span className={cn("mt-0.5 shrink-0 rounded px-1 font-mono text-[10px]", x.role === "customer" ? "bg-indigo-soft text-indigo" : "bg-cyan-soft text-cyan")}>
              {x.role === "customer" ? "C" : "A"}{x.turn_index}
            </span>
            <span className={cn("text-ink/90", x.sentiment === "negative" && x.role === "customer" && "text-neg/90")}>{x.text}</span>
          </p>
        ))}
      </div>
      <button onClick={() => openConversation(e.conversation_id, e.message_ids)} className="focus-ring mt-2.5 self-start rounded text-[11px] font-medium text-violet hover:underline">
        Open full transcript →
      </button>
    </motion.div>
  );
}

function RecommendationCard({ r, i }: { r: Recommendation; i: number }) {
  const { openConversation } = useEvidence();
  const tone = r.priority === "High" ? "negative" : r.priority === "Medium" ? "warning" : "indigo";
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 * i }} className="rounded-xl border border-line bg-gradient-to-b from-white/[0.03] to-transparent p-4">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2"><span className="num text-xs text-faint">#{r.rank}</span><h4 className="text-sm font-semibold">{r.concern}</h4></div>
        <Badge tone={tone}>{r.priority}</Badge>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">{r.finding}</p>
      <div className="mt-3 grid gap-2 text-xs sm:grid-cols-2">
        <div className="rounded-lg bg-white/[0.03] p-2.5"><p className="label">Suggested action</p><p className="mt-1 text-ink">{r.suggested_action}</p></div>
        <div className="rounded-lg bg-white/[0.03] p-2.5"><p className="label">Decision owner</p><p className="mt-1 text-ink">{r.decision_owner}</p>
          <p className="mt-1 text-faint">Driver: {r.supporting_metric.label}</p></div>
      </div>
      <p className="mt-2 text-[11px] text-faint">{r.rationale} {r.uncertainty}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {r.evidence.map((id) => <button key={id} onClick={() => openConversation(id)} className="focus-ring rounded-md border border-line px-1.5 py-0.5 font-mono text-[10px] text-cyan hover:bg-white/5">{id}</button>)}
      </div>
    </motion.div>
  );
}

export function ResponseView({ r }: { r: ChatResponse }) {
  const { ask, busy } = useApp();
  const [showChecks, setShowChecks] = useState(false);
  const kpis = r.charts.filter((c) => c.chart_type === "kpi");
  const charts = r.charts.filter((c) => c.chart_type !== "kpi");
  const qa = r.quality_status;
  const statusTone = r.status === "completed" ? "positive" : r.status === "unsupported" || r.status === "insufficient_data" ? "warning" : "negative";
  const mm = r.model_metadata;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        <Badge tone="indigo"><Sparkles className="h-3 w-3" />{humanize(r.plan.category)}</Badge>
        <Badge tone={statusTone}>{humanize(r.status)}</Badge>
        <Tip content={`Intent: ${mm.intent_source}; explanation: ${mm.explanation_source}. ${mm.reason ? `Model note: ${String(mm.reason).slice(0, 140)}` : ""}`}>
          <span><Badge tone={mm.mode === "llm" ? "violet" : "default"}><BrainCircuit className="h-3 w-3" />{mm.mode === "llm" ? `${({ gemini: "Gemini", "vertex-ai": "Vertex AI", groq: "Groq", local: "Local LLM" } as Record<string, string>)[mm.provider] ?? "LLM"} (${mm.model})` : "Deterministic explainer"}</Badge></span>
        </Tip>
        <button onClick={() => setShowChecks((s) => !s)} className="focus-ring rounded-full" aria-expanded={showChecks}>
          <Badge tone={qa.status === "pass" ? "positive" : qa.status === "warn" ? "warning" : "negative"}><ShieldCheck className="h-3 w-3" />QA {qa.passed}/{qa.total}</Badge>
        </button>
        <Badge><Clock className="h-3 w-3" />{ms(r.latency_ms)}</Badge>
        <Badge>{r.dataset_scope.window.label}</Badge>
        <Link to={`/harness/${r.request_id}`} className="focus-ring rounded-full"><Badge tone="cyan"><Network className="h-3 w-3" />Trace</Badge></Link>
      </div>
      {showChecks && (
        <ul className="grid gap-1.5 rounded-xl border border-line bg-white/[0.02] p-3 text-xs sm:grid-cols-2">
          {qa.checks.map((c) => (
            <li key={c.check} className="flex items-start gap-2">
              {c.passed ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pos" /> : <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" />}
              <span><span className="text-ink">{humanize(c.check)}</span> <span className="text-faint">— {c.detail}</span></span>
            </li>
          ))}
        </ul>
      )}

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
        <h2 className="text-lg font-semibold leading-snug tracking-tight text-ink sm:text-xl">{r.headline}</h2>
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-ink/80">{r.answer}</p>
        {(r.plan.notes.length > 0 || r.dataset_scope.window.explanation) && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {r.dataset_scope.window.rule !== "all" && <span className="inline-flex items-start gap-1.5 rounded-lg border border-line bg-white/[0.02] px-2 py-1 text-[11px] text-muted"><CalendarDays className="mt-px h-3 w-3 shrink-0" aria-hidden />{r.dataset_scope.window.explanation}</span>}
            {r.plan.notes.map((n) => <span key={n} className="rounded-lg border border-violet/20 bg-violet/[0.06] px-2 py-1 text-[11px] text-violet">{n}</span>)}
          </div>
        )}
      </motion.div>

      {r.human_review_required && (
        <div className="flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn/[0.06] px-4 py-3 text-xs text-ink/90" role="note">
          <UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
          <span><b className="text-warn">Human review required.</b> This is decision support. A named owner should review the cited conversations before acting; it is not a performance assessment.</span>
        </div>
      )}

      {kpis.map((k, i) => <ChartCard key={k.chart_id} spec={k} delay={0.05 * i} />)}

      {charts.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-2">
          {charts.map((c, i) => {
            // Full width for wide chart types, and for a half-width chart that would otherwise sit alone in its row.
            const half = charts.filter((x) => !FULL_WIDTH.has(x.chart_type));
            const lone = !FULL_WIDTH.has(c.chart_type) && half.length % 2 === 1 && half[half.length - 1] === c;
            return <ChartCard key={c.chart_id} spec={c} delay={0.08 * i} className={cn((FULL_WIDTH.has(c.chart_type) || lone) && "xl:col-span-2")} />;
          })}
        </div>
      )}
      {r.graphs.map((g) => <RelationGraph key={g.graph_id} spec={g} />)}

      {r.recommendations.length > 0 && (
        <section aria-labelledby={`recs-${r.request_id}`}>
          <h3 id={`recs-${r.request_id}`} className="mb-2.5 flex items-center gap-2 text-sm font-semibold"><Lightbulb className="h-4 w-4 text-mix" />Recommendations for leadership</h3>
          <div className="grid gap-3 lg:grid-cols-2">{r.recommendations.map((x, i) => <RecommendationCard key={x.topic} r={x} i={i} />)}</div>
        </section>
      )}

      {r.key_points.length > 0 && (
        <Card>
          <CardHeader title="Key points" icon={<Quote className="h-4 w-4" />} />
          <ul className="space-y-1.5 px-5 pb-4 pt-3 text-sm text-ink/85">
            {r.key_points.map((k) => <li key={k} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-cyan" />{k}</li>)}
          </ul>
        </Card>
      )}

      {r.evidence.length > 0 && (
        <section aria-labelledby={`ev-${r.request_id}`}>
          <h3 id={`ev-${r.request_id}`} className="mb-2.5 flex items-center gap-2 text-sm font-semibold"><FileSearch className="h-4 w-4 text-cyan" />Supporting evidence
            <span className="text-xs font-normal text-faint">{r.evidence.length} source conversations</span></h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{r.evidence.map((e, i) => <EvidenceCard key={e.evidence_id} e={e} i={i} />)}</div>
        </section>
      )}

      {(r.uncertainty_notes.length > 0 || r.method_notes.length > 0) && (
        <details className="group rounded-xl border border-line bg-white/[0.02]" open={r.uncertainty_notes.length > 0}>
          <summary className="focus-ring flex cursor-pointer list-none items-center gap-2 rounded-xl px-4 py-3 text-sm font-semibold">
            <CircleHelp className="h-4 w-4 text-warn" />Uncertainty & method<span className="text-xs font-normal text-faint">{r.uncertainty_notes.length} caveats</span>
            <ChevronDown className="ml-auto h-4 w-4 text-faint transition group-open:rotate-180" />
          </summary>
          <div className="grid gap-4 px-4 pb-4 text-xs leading-relaxed md:grid-cols-2">
            <ul className="space-y-1.5 text-ink/80">{r.uncertainty_notes.map((n) => <li key={n} className="flex gap-2"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-warn" />{n}</li>)}</ul>
            <ul className="space-y-1.5 text-muted">{r.method_notes.map((n) => <li key={n}>• {n}</li>)}</ul>
          </div>
        </details>
      )}

      {r.follow_up_questions.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {r.follow_up_questions.map((q) => (
            <button key={q} disabled={busy} onClick={() => ask(q)} className="focus-ring rounded-full border border-indigo/25 bg-indigo/[0.07] px-3 py-1.5 text-xs text-ink transition hover:border-indigo/50 hover:bg-indigo/15 disabled:opacity-40">
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
