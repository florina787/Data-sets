import { motion } from "framer-motion";
import {
  AlertTriangle, BookOpen, BrainCircuit, Gauge, CalendarDays, CheckCircle2, ChevronDown, CircleHelp, Clock, FileSearch, Lightbulb, Network, Quote, ShieldCheck, Sparkles, UserCheck, Zap,
} from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "@/app/AppState";
import { ChartCard } from "@/components/charts/ChartCard";
import { Badge, Card, CardHeader, SentimentBadge, Tip } from "@/components/common/ui";
import { useEvidence } from "@/components/evidence/EvidenceContext";
import { DashboardView } from "@/components/insights/DashboardView";
import { DecisionReplay } from "@/components/insights/DecisionReplay";
import { EvidenceReview } from "@/components/insights/EvidenceReview";
import { RootCausePanel } from "@/components/insights/RootCausePanel";
import { RoutingStrip } from "@/components/insights/RoutingStrip";
import { XRayPanel } from "@/components/insights/XRayPanel";
import { RelationGraph } from "@/components/workflow/RelationGraph";
import { humanize, ms } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { ChatResponse, Evidence, Recommendation } from "@/types/api";

const FULL_WIDTH = new Set(["timeline", "heatmap", "table"]);

/** Top-N statements: each row is a real customer statement with its count and the conversations that contain it. */
function StatementsTable({ r }: { r: ChatResponse }) {
  const { openConversation } = useEvidence();
  const rows = r.rankings as { rank: number; statement: string; mentions: number; conversations: number; mean_score: number;
    share_of_polarity: number; example_conversation_ids?: string[]; example_message_ids?: string[] }[];
  if (!rows.length) return null;
  return (
    <Card>
      <CardHeader title="Statements, ranked" icon={<Quote className="h-4 w-4" />} />
      <div className="overflow-x-auto px-2 pb-3">
        <table className="w-full min-w-[520px] text-left text-xs" data-testid="statements-table">
          <thead className="text-faint"><tr>
            <th className="px-3 py-2 font-medium">#</th><th className="px-3 py-2 font-medium">Statement</th>
            <th className="px-3 py-2 text-right font-medium">Mentions</th><th className="px-3 py-2 text-right font-medium">Conversations</th>
            <th className="px-3 py-2 text-right font-medium">Share</th><th className="px-3 py-2 font-medium">Examples</th>
          </tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.rank} className="border-t border-line align-top">
                <td className="num px-3 py-2 text-faint">{row.rank}</td>
                <td className="px-3 py-2 text-ink">“{row.statement}”</td>
                <td className="num px-3 py-2 text-right">{row.mentions.toLocaleString()}</td>
                <td className="num px-3 py-2 text-right">{row.conversations.toLocaleString()}</td>
                <td className="num px-3 py-2 text-right">{(row.share_of_polarity * 100).toFixed(1)}%</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1">
                    {(row.example_conversation_ids ?? []).map((cid, i) => (
                      <button key={`${cid}-${i}`} onClick={() => openConversation(cid, row.example_message_ids?.[i] ? [row.example_message_ids[i]] : [])}
                        className="focus-ring num rounded border border-line px-1.5 py-0.5 text-[10px] text-cyan hover:border-cyan/50">{cid}</button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

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
      {e.method_scores && Object.keys(e.method_scores).length > 0 && <MethodRanks e={e} />}
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

const METHOD_NAME = { dense: "MiniLM", lsa: "LSA" } as const;

/** Which retrieval methods found this passage, and at what rank (hybrid = weighted reciprocal rank fusion of both). */
function MethodRanks({ e }: { e: Evidence }) {
  const ms_ = e.method_scores ?? {};
  return (
    <div className="mt-1.5 flex flex-wrap items-center gap-1 text-[10px]" data-testid="method-ranks">
      {e.retrieval_method === "hybrid" && <Tip content="Ranked by weighted Reciprocal Rank Fusion of the MiniLM (dense) and LSA (sparse) rankings."><span><Badge tone="violet">hybrid RRF</Badge></span></Tip>}
      {(["dense", "lsa"] as const).map((k) => ms_[k] ? (
        <Tip key={k} content={`${METHOD_NAME[k]} ranked this conversation #${ms_[k]!.rank} (cosine ${ms_[k]!.similarity.toFixed(2)}).`}>
          <span><Badge>{METHOD_NAME[k]} #{ms_[k]!.rank}</Badge></span></Tip>
      ) : e.retrieval_method === "hybrid" ? <Badge key={k} className="opacity-60">{METHOD_NAME[k]} —</Badge> : null)}
    </div>
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
  const [view, setView] = useState<"answer" | "dashboard">("answer");
  const kpis = r.charts.filter((c) => c.chart_type === "kpi");
  const charts = r.charts.filter((c) => c.chart_type !== "kpi");
  const qa = r.quality_status;
  const statusTone = r.status === "completed" ? "positive" : r.status === "unsupported" || r.status === "insufficient_data" ? "warning" : "negative";
  const mm = r.model_metadata;
  const general = mm.explanation_source === "general_knowledge";
  const g = r.groundedness;
  const categoryLabel = r.plan.category !== "unsupported" ? humanize(r.plan.category)
    : general ? "Outside the dataset" : r.headline === "Which analysis did you mean?" ? "Needs clarification" : "Unsupported";
  const statusLabel = general ? "Model's own answer" : categoryLabel === "Needs clarification" ? "Clarify" : humanize(r.status);
  if (r.routing?.route === "fast_path") {
    return (
      <div className="space-y-3" data-testid="small-talk">
        <p className="text-sm leading-relaxed text-ink"><span className="font-semibold">{r.headline}</span> <span className="text-ink/80">{r.answer}</span></p>
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <Tip content={r.routing.reason}><span><Badge><Zap className="h-3 w-3" />Fast path · no model</Badge></span></Tip>
          <Badge><Clock className="h-3 w-3" />{ms(r.latency_ms)}</Badge>
        </div>
        <div className="flex flex-wrap gap-2">
          {r.follow_up_questions.map((q) => (
            <button key={q} disabled={busy} onClick={() => ask(q)} className="focus-ring rounded-full border border-indigo/25 bg-indigo/[0.07] px-3 py-1.5 text-xs text-ink transition hover:border-indigo/50 hover:bg-indigo/15 disabled:opacity-40">
              {q}
            </button>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
        <Badge tone="indigo"><Sparkles className="h-3 w-3" />{categoryLabel}</Badge>
        <Badge tone={general ? "violet" : statusTone}>{statusLabel}</Badge>
        {g && (
          <Tip content={g.reasons.join(" · ")}>
            <span data-testid="groundedness">
              <Badge tone={g.basis === "general_knowledge" ? "warning" : g.risk === "low" ? "positive" : g.risk === "medium" ? "warning" : "negative"}>
                <Gauge className="h-3 w-3" />{g.label}{g.score !== null ? ` · ${g.risk} hallucination risk` : ""}
              </Badge>
            </span>
          </Tip>
        )}
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
      <RoutingStrip r={r} />
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
        {general && (
          <div className="mt-3 flex items-start gap-2.5 rounded-xl border border-warn/30 bg-warn/[0.06] px-4 py-3 text-xs text-ink/90" role="note" data-testid="general-answer-banner">
            <BookOpen className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
            <span><b className="text-warn">Model's own answer, not from the dataset.</b> No analysis in this copilot answers this question, so the language model replied from its general knowledge. Nothing here was computed from, or checked against, the conversations. For answers grounded in the data, try one of the suggested questions below.</span>
          </div>
        )}
        <p className="mt-2 max-w-4xl text-sm leading-relaxed text-ink/80">{general ? r.answer.replace(/^Model's own answer, not from the dataset\.\s*/, "") : r.answer}</p>
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

      {r.plan.category === "top_statements" && <StatementsTable r={r} />}
      {r.root_cause && <RootCausePanel panel={r.root_cause} />}
      {r.xray && <XRayPanel panel={r.xray} />}

      {r.dashboard && (r.charts.length > 0) && (
        <div role="tablist" aria-label="Result view" className="inline-flex rounded-xl border border-line bg-white/[0.02] p-0.5 text-xs">
          {(["answer", "dashboard"] as const).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)} data-testid={`view-${v}`}
              className={cn("focus-ring rounded-lg px-3 py-1 font-medium transition", view === v ? "bg-indigo/20 text-ink" : "text-faint hover:text-ink")}>
              {v === "answer" ? "Answer" : "Dashboard"}
            </button>
          ))}
        </div>
      )}

      {view === "dashboard" && r.dashboard ? <DashboardView r={r} /> : <>
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
      </>}

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

      {r.evidence_review && <EvidenceReview review={r.evidence_review} />}

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

      <DecisionReplay requestId={r.request_id} />

      {r.follow_up_questions.length > 0 && r.plan.category === "unsupported" && (
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted" data-testid="nudge-heading">
          <Lightbulb className="h-3.5 w-3.5 text-indigo" aria-hidden />Closest questions I can answer from the data
        </p>
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
