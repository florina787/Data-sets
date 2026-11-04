import { AlertTriangle, ClipboardList, FileSearch, Lightbulb, ScrollText, ShieldAlert, TrendingDown, TrendingUp } from "lucide-react";
import { useState } from "react";
import { DataGrid } from "@/components/ChartCard";
import { Badge, Button, cn } from "@/components/ui";
import { STATUS_LABEL } from "../format";
import type { Insight, MessageContext, MessageResponse } from "../types";
import type { Turn } from "../useConversation";
import { ApprovalPanel } from "./ApprovalPanel";
import { DataFreshnessIndicator } from "./DataFreshnessIndicator";
import { DynamicDashboardRenderer } from "./DynamicDashboardRenderer";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { ImplementationRoadmap } from "./ImplementationRoadmap";
import { RecommendationPanel } from "./RecommendationPanel";
import { ScenarioControls } from "./ScenarioControls";
import { WorkflowProgress } from "./WorkflowProgress";

const SECTIONS: { id: Insight["section"]; label: string; icon: any }[] = [
  { id: "current_state", label: "Current state", icon: ClipboardList }, { id: "finding", label: "Findings", icon: FileSearch },
  { id: "risk", label: "Risks", icon: AlertTriangle }, { id: "opportunity", label: "Opportunities", icon: Lightbulb },
  { id: "limitation", label: "Limitations & assumptions", icon: ScrollText }];
const SEV = { info: "text-ink/90", positive: "text-pos", warning: "text-warn", critical: "text-crit" } as const;
const SCENARIO_PERSONAS = new Set(["cio", "institutional_pm", "ceo", "cfo", "risk_compliance"]);

function Insights({ items }: { items: Insight[] }) {
  if (!items.length) return null;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {SECTIONS.map(({ id, label, icon: Icon }) => {
        const xs = items.filter((i) => i.section === id);
        if (!xs.length) return null;
        return (
          <section key={id} className="rounded-xl border border-line bg-card p-3.5" aria-label={label}>
            <h3 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted"><Icon className="h-3.5 w-3.5" />{label}</h3>
            <ul className="space-y-2 text-sm">
              {xs.map((i) => (
                <li key={i.id}>
                  <div className={cn("flex items-start gap-1.5 font-medium", SEV[i.severity])}>
                    {i.severity === "positive" ? <TrendingUp className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : i.severity === "warning" || i.severity === "critical" ? <TrendingDown className="mt-0.5 h-3.5 w-3.5 shrink-0" /> : null}
                    <span>{i.title}</span>
                  </div>
                  {i.detail && <p className="text-xs text-muted">{i.detail}</p>}
                  {i.evidence.length > 0 && <p className="text-[10px] text-muted/80">evidence: {i.evidence.map((e) => `${e.agent}.${e.fact}`).join(", ")}</p>}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

function Planning({ t }: { t: Turn }) {
  return (
    <div className="space-y-4" aria-busy="true">
      <div className="rounded-xl border border-line bg-card p-4">
        <p className="mb-3 text-sm text-muted">Analysing: <span className="text-ink">{t.question}</span></p>
        <WorkflowProgress stages={t.stages} agents={t.agents} plan={t.plan} live />
      </div>
      {t.intent && t.intent.charts.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-2">
          {t.intent.charts.slice(0, 4).map((c) => (
            <div key={c} className="h-48 rounded-xl border border-dashed border-line bg-card/40 p-4 text-xs text-muted motion-safe:animate-pulse">
              Preparing {c.replace(/_/g, " ")}…
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function IntelligenceWorkspace({ turn, onFollowup, busy, onComposerText }: { turn?: Turn; busy: boolean;
  onFollowup: (q: string, c?: MessageContext) => void; onComposerText: (t: string) => void }) {
  const [evidence, setEvidence] = useState(false);
  if (!turn) return null;
  if (!turn.response) return turn.state === "streaming" ? <Planning t={turn} /> : null;
  const r: MessageResponse = turn.response;
  const showScenario = r.intent.intent === "scenario" || (SCENARIO_PERSONAS.has(r.persona) && ["aum_profitability", "firm_overview", "executive_briefing", "concentration_risk"].includes(r.intent.intent) && r.status !== "denied");
  return (
    <div className="space-y-5" data-testid="workspace">
      <header className="flex flex-wrap items-center gap-2">
        <Badge tone="gold">{r.intent.label}</Badge>
        <Badge tone={r.status === "complete" ? "good" : r.status === "denied" ? "crit" : "warn"}>{STATUS_LABEL[r.status]}</Badge>
        {r.intent.time_horizon_months && <Badge>{r.intent.time_horizon_months} months</Badge>}
        <DataFreshnessIndicator asOf={r.data_freshness.as_of} refreshedAt={r.data_freshness.refreshed_at} synthetic={r.data_freshness.synthetic} sources={r.data_freshness.sources} />
        <Button size="sm" variant="secondary" className="ml-auto" onClick={() => setEvidence(true)}><FileSearch className="h-3.5 w-3.5" />Evidence & trace</Button>
      </header>
      <section className="rounded-2xl border border-line bg-gradient-to-b from-card to-card/60 p-5" aria-label="FLO answer">
        <h2 className="text-lg font-semibold leading-snug sm:text-xl" data-testid="workspace-headline">{r.answer.headline}</h2>
        {r.answer.summary.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink/90">{r.answer.summary.map((s) => <li key={s}>{s}</li>)}</ul>}
        {r.answer.body && (
          <details className="mt-3 text-sm text-ink/85" open={r.status !== "complete" || r.charts.length === 0}>
            <summary className="cursor-pointer text-xs text-muted hover:text-ink">Full explanation from the specialist agents</summary>
            <p className="mt-2 whitespace-pre-wrap leading-relaxed">{r.answer.body}</p>
          </details>
        )}
        {r.warnings.length > 0 && (
          <ul className="mt-3 space-y-0.5 text-xs text-warn">{r.warnings.map((w) => <li key={w} className="flex items-start gap-1"><ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />{w}</li>)}</ul>
        )}
      </section>
      {r.discovery && (
        <section aria-label="Discovery" className="rounded-xl border border-blue/30 bg-blue/5 p-4">
          <h3 className="mb-1 text-sm font-semibold">Let's complete the picture</h3>
          <p className="mb-2 text-xs text-muted">Known: {r.discovery.known.join(", ") || "nothing yet"} · Still needed: {r.discovery.missing.join(", ") || "—"}</p>
          <ul className="space-y-1">
            {r.discovery.questions.map((q) => (
              <li key={q}><button onClick={() => onComposerText(q.replace(/\?$/, ": "))} className="text-left text-sm text-ink/90 hover:text-gold">• {q}</button></li>
            ))}
          </ul>
        </section>
      )}
      <DynamicDashboardRenderer kpis={r.kpis} charts={r.charts} onFollowup={onFollowup} />
      {showScenario && <ScenarioControls initial={r.intent.modifiers?.scenario} onRun={onFollowup} disabled={busy} />}
      <Insights items={r.insights} />
      <RecommendationPanel recs={r.recommendations} onAsk={(q) => onFollowup(q)} />
      {r.implementation_plan && <ImplementationRoadmap plan={r.implementation_plan} />}
      <ApprovalPanel items={r.approval_requirements} />
      {r.tables.map((t) => (
        <section key={t.table_id} aria-label={t.title} className="rounded-xl border border-line bg-card p-3.5">
          <h3 className="mb-2 text-sm font-semibold">{t.title}</h3>
          <DataGrid rows={t.rows.map((row) => Object.fromEntries(t.columns.map((c, i) => [c, row[i] as any])))} />
          {t.table_id === "client_choices" && (
            <div className="mt-2 flex flex-wrap gap-1.5">{t.rows.map((row) => (
              <button key={String(row[0])} onClick={() => onFollowup(`${r.intent.intent === "retirement_strategy" ? "Build a retirement strategy" : "Prepare a portfolio review"} for ${row[0]}.`, { client_id: String(row[0]) })}
                className="rounded-full border border-line px-2.5 py-1 text-xs hover:border-gold/60">{String(row[0])}</button>))}</div>
          )}
        </section>
      ))}
      {r.suggested_followups.length > 0 && (
        <section aria-label="Continue the conversation" className="flex flex-wrap gap-1.5">
          {r.suggested_followups.map((f) => <button key={f} onClick={() => onFollowup(f)} className="rounded-full border border-line px-3 py-1.5 text-xs hover:border-gold/60">{f}</button>)}
        </section>
      )}
      <EvidenceDrawer r={r} open={evidence} onClose={() => setEvidence(false)} />
    </div>
  );
}
