import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, BrainCircuit, CheckCircle2, Crown, Plane, ScanSearch, ShieldCheck, Stethoscope } from "lucide-react";
import { Badge } from "./ui";

export type QwenAnswer = {
  type: "qwen_answer"; headline: string; summary: string; key_findings: string[]; recommended_next_steps: string[]; limitations: string[]; general_knowledge?: boolean;
  meta: { model: string; runtime: string; latency_ms: number; first_token_ms: number | null; tokens_per_s: number | null; prompt_tokens: number; completion_tokens: number; cached: boolean };
  challenger: { verdict: string; issues: { issue: string; field?: string; text?: string }[]; removed: number; claims_checked: number; unsupported: number; checks: string[] };
  governance?: { checks: { check: string; ok: boolean; detail?: string }[]; pending_approvals: string[]; ok: boolean };
};
export type QwenStatus = { type: "qwen_status"; available: boolean; reason?: string; error?: string; rejected?: boolean; note: string; challenger?: QwenAnswer["challenger"] };

export const FOUR = [
  { family: "diagnostics", icon: Stethoscope, tag: "Q1 · Aircraft Diagnostics", q: "Why is aircraft AC-204 showing abnormal vibration, and what should engineering investigate?" },
  { family: "recovery", icon: Plane, tag: "Q2 · Aircraft Recovery", q: "Which recovery option could return AC-204 to service fastest, considering spare parts, maintenance scheduling, and engineering approval?" },
  { family: "modernization", icon: ScanSearch, tag: "Q3 · Legacy Modernization", q: "How can we modernize our legacy aircraft maintenance system using APIs, MCP, and AI without replacing the existing platform?" },
  { family: "executive", icon: Crown, tag: "Q4 · Executive Intelligence", q: "What is affecting fleet readiness, and which maintenance improvements could reduce downtime and cost?" },
];

export function FourQuestionCards({ onAsk, disabled }: { onAsk: (q: string) => void; disabled?: boolean }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2" data-testid="four-questions">
      {FOUR.map(({ icon: Icon, tag, q, family }, i) => (
        <motion.button key={q} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + i * 0.05 }} onClick={() => onAsk(q)} disabled={disabled}
          data-family={family} className="group flex gap-3 rounded-2xl border border-token bg-[var(--panel)] p-4 text-left transition hover:border-indigo/40 hover:bg-[var(--panel-2)]">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo/25 to-cyan/10 text-cyan ring-1 ring-[var(--border)]"><Icon className="h-4 w-4" /></div>
          <div className="min-w-0">
            <p className="label">{tag}</p>
            <p className="mt-1 text-sm leading-snug">{q}</p>
          </div>
          <ArrowRight className="ml-auto mt-1 h-4 w-4 shrink-0 text-faint opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" />
        </motion.button>
      ))}
    </div>
  );
}

export function QwenAnswerCard({ b }: { b: QwenAnswer }) {
  const m = b.meta;
  const verdictTone = b.challenger.verdict === "pass" ? "teal" : "amber";
  return (
    <motion.section initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="panel glow overflow-hidden" data-testid="qwen-answer">
      <div className="flex flex-wrap items-center gap-2 border-b border-token px-5 py-3">
        <BrainCircuit className="h-4 w-4 text-cyan" aria-hidden />
        <span className="text-xs font-medium">{b.general_knowledge ? "General knowledge · Local Qwen" : "Explained by Local Qwen"}</span>
        <Badge tone="gold">{m.model}</Badge>
        <Badge tone="gray">{m.runtime}</Badge>
        <Badge tone={verdictTone} title={b.challenger.checks.join(" · ")}><ShieldCheck className="h-3 w-3" />Evidence Challenger: {b.challenger.verdict.replace(/_/g, " ")}</Badge>
        <span className="num ml-auto text-[11px] text-faint">{m.cached ? "cached · " : ""}{m.latency_ms} ms · TTFT {m.first_token_ms ?? "-"} ms · {m.tokens_per_s ?? "-"} tok/s · {m.prompt_tokens}+{m.completion_tokens} tok</span>
      </div>
      <div className="space-y-3 px-5 py-4">
        <h3 className="text-base font-semibold leading-snug">{b.headline}</h3>
        <p className="muted text-sm leading-relaxed">{b.summary}</p>
        <div className="grid gap-4 md:grid-cols-3">
          {b.key_findings.length > 0 && <List title="Key findings" items={b.key_findings} />}
          {b.recommended_next_steps.length > 0 && <List title="Recommended next steps" items={b.recommended_next_steps} />}
          {b.limitations.length > 0 && <List title="Confidence & limitations" items={b.limitations} warn />}
        </div>
        {b.challenger.removed > 0 && (
          <p className="text-[11px] text-warn">{b.challenger.removed} unsupported item(s) removed by the Evidence Challenger: {b.challenger.issues.slice(0, 3).map((i) => i.issue).join("; ")}</p>
        )}
        {b.governance && (
          <div className="flex flex-wrap gap-1.5 border-t border-token pt-3">
            {b.governance.checks.map((c) => <Badge key={c.check} tone={c.ok ? "teal" : "red"}>{c.ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}{c.check}</Badge>)}
          </div>
        )}
      </div>
    </motion.section>
  );
}

function List({ title, items, warn }: { title: string; items: string[]; warn?: boolean }) {
  return (
    <div>
      <p className="label mb-1.5">{title}</p>
      <ul className="space-y-1 text-sm">
        {items.map((x) => <li key={x} className="flex gap-2"><span className={`mt-2 h-1.5 w-1.5 shrink-0 rounded-full ${warn ? "bg-warn" : "bg-cyan"}`} />{x}</li>)}
      </ul>
    </div>
  );
}

export function QwenStatusCard({ b }: { b: QwenStatus }) {
  return (
    <div role="status" data-testid="qwen-status" className="flex items-start gap-3 rounded-2xl border border-warn/30 bg-warn/[0.06] p-4 text-sm">
      <BrainCircuit className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
      <div className="min-w-0">
        <p className="font-medium">{!b.available ? "Local Qwen is not available, so this answer is the deterministic evidence summary" : b.rejected ? "Qwen's explanation was rejected by the Evidence Challenger" : "Qwen did not finish an explanation"}</p>
        <p className="muted mt-0.5 text-xs">{b.note} {b.reason ? `Reason: ${b.reason}` : ""}{b.error ? `Error: ${b.error}` : ""}</p>
        {b.challenger?.issues?.length ? <p className="mt-1 text-[11px] text-warn">Unsupported: {b.challenger.issues.slice(0, 4).map((i) => i.issue).join("; ")}</p> : null}
      </div>
    </div>
  );
}
