import { AlertTriangle, LayoutDashboard, ShieldAlert, Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import { Badge, cn } from "@/components/ui";
import { STATUS_LABEL } from "../format";
import type { Turn } from "../useConversation";
import { AgentTimeline } from "./AgentTimeline";
import { FinancialChartRenderer } from "./FinancialChartRenderer";
import { FinancialKPICard } from "./FinancialKPICard";
import { WorkflowProgress } from "./WorkflowProgress";

const TONE: Record<string, "good" | "warn" | "crit" | "blue" | "neutral"> = { complete: "good", partial: "warn", denied: "crit", needs_input: "blue",
  rejected: "crit", cancelled: "neutral", error: "crit" };

export function FloConversation({ turns, selected, onSelect, onFollowup, onChartFollowup }: {
  turns: Turn[]; selected: number; onSelect: (i: number) => void; onFollowup: (q: string) => void;
  onChartFollowup?: (q: string, c?: import("../types").MessageContext) => void;
}) {
  const end = useRef<HTMLDivElement>(null);
  const last = turns[turns.length - 1];
  useEffect(() => { end.current?.scrollIntoView({ block: "end", behavior: "smooth" }); }, [turns.length, last?.state]);
  return (
    <div role="log" aria-label="Conversation with FLO" aria-live="polite" className="space-y-5">
      {turns.map((t, i) => {
        const r = t.response;
        return (
          <div key={t.key} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-blue/15 px-3.5 py-2 text-sm text-ink ring-1 ring-blue/25">{t.question}</div>
            </div>
            <div className={cn("rounded-2xl rounded-bl-md border bg-card p-3.5 transition-colors", i === selected ? "border-gold/50" : "border-line")}
              data-testid="flo-turn" data-status={r?.status ?? t.state}>
              <div className="mb-2 flex items-center gap-2">
                <span className="grid h-6 w-6 place-items-center rounded-full bg-bg ring-1 ring-gold/50"><Sparkles className="h-3.5 w-3.5 text-gold" /></span>
                <span className="text-xs font-semibold tracking-wide">FLO</span>
                {r && <Badge tone={TONE[r.status]}>{STATUS_LABEL[r.status]}</Badge>}
                {(r?.intent ?? t.intent) && <span className="truncate text-[11px] text-muted">{(r?.intent ?? t.intent)!.label}</span>}
              </div>
              {t.state === "streaming" && <WorkflowProgress stages={t.stages} agents={t.agents} plan={t.plan} live />}
              {t.state === "error" && (
                <p className="flex items-start gap-2 text-sm text-crit" role="alert"><AlertTriangle className="mt-0.5 h-4 w-4" />{t.error}</p>
              )}
              {r && (
                <div className="space-y-2">
                  <p className="text-[15px] font-medium leading-snug text-ink" data-testid="flo-headline">
                    {r.status === "denied" && <ShieldAlert className="mr-1 inline h-4 w-4 text-warn" />}{r.answer.headline}
                  </p>
                  {r.answer.summary.length > 0 && (
                    <ul className="list-disc space-y-0.5 pl-4 text-sm text-ink/85">{r.answer.summary.map((s) => <li key={s}>{s}</li>)}</ul>
                  )}
                  {(r.status === "denied" || r.status === "needs_input" || r.intent.intent === "greeting" || r.intent.intent === "help") && r.answer.body && (
                    <p className="text-sm text-muted">{r.answer.body}</p>
                  )}
                  {i === turns.length - 1 && r.kpis.length > 0 && (
                    <div role="group" aria-label="Headline metrics" className="grid grid-cols-2 gap-2 pt-1 sm:grid-cols-3">
                      {r.kpis.slice(0, 3).map((k, j) => <FinancialKPICard key={k.id} k={k} index={j} inline />)}
                    </div>
                  )}
                  {i === turns.length - 1 && r.charts[0] && (
                    <div className="pt-1">
                      <FinancialChartRenderer spec={r.charts[0]} onFollowup={onChartFollowup ?? ((q) => onFollowup(q))} height={210} inline />
                    </div>
                  )}
                  {r.workflow.agent_runs && r.workflow.agent_runs.length > 0 && <AgentTimeline runs={r.workflow.agent_runs} latency={r.workflow.latency_ms} />}
                  {(r.charts.length > 0 || r.kpis.length > 0 || r.recommendations.length > 0) && (
                    <button onClick={() => onSelect(i)} className={cn("flex items-center gap-1 text-xs", i === selected ? "text-gold" : "text-muted hover:text-ink")}>
                      <LayoutDashboard className="h-3.5 w-3.5 shrink-0" />
                      <span>{i === selected ? "In workspace" : "Show in workspace"} · {r.kpis.length} KPIs, {r.charts.length} charts, {r.recommendations.length} actions</span>
                    </button>
                  )}
                  {i === turns.length - 1 && r.suggested_followups.length > 0 && (
                    <div role="group" className="flex flex-wrap gap-1.5 pt-1" aria-label="Suggested follow-ups">
                      {r.suggested_followups.map((f) => (
                        <button key={f} onClick={() => onFollowup(f)} className="rounded-full border border-line px-2.5 py-1 text-xs text-ink/85 hover:border-gold/60">{f}</button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
      <div ref={end} />
    </div>
  );
}
