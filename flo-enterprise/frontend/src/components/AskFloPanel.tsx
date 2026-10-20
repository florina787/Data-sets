import { useMutation } from "@tanstack/react-query";
import { BookOpen, Bot, ChevronDown, ShieldCheck, Send, X } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { LANGS, t, type Lang } from "@/lib/i18n";
import { Badge, Button, ErrorState, Select, Spinner } from "./ui";

type Answer = {
  heading: string; text: string; language: string; language_note: string; route: string; agents: string[]; workflow_id: string;
  citations: { document_id: string; title: string; section: string; version: string }[]; warnings: string[];
  errors: { agent: string; failure_class: string; message: string }[]; approvals: { id: string; status: string; action: string }[];
  tool_calls: { tool: string; agent: string; decision: string; status?: string; rule?: string; latency_ms?: number }[];
  policy_decisions: { action: string; allowed: boolean }[]; injection?: { flagged: boolean; severity: string }; trace_ids: string[]; model_mode: string;
};

const SUGGEST: Record<string, string[]> = {
  executive: ["Why did AUM increase while profitability declined?", "Which decisions delivered measurable value?", "Prepare a board report"],
  cio: ["Analyze concentration and simulate a 25% equity market drop", "How did funds perform against benchmarks?", "What happened in markets last month?"],
  wealth_advisor: ["Prepare a portfolio review for client ", "Compare low-fee ETF products", "What is the client communications approval policy?"],
  compliance_officer: ["What is the client communications approval policy?", "Quelle est la politique d'approbation des communications?", "Summarize suitability procedures"],
  ai_admin: ["Why is an agent failing? Investigate the incident.", "Run data quality checks", "Summarize evaluation results"],
};

export function AskFloPanel() {
  const { askOpen, closeAsk, askCtx, me, lang } = useApp();
  const [q, setQ] = useState("");
  const [answerLang, setAnswerLang] = useState<Lang>(lang);
  const [showTrace, setShowTrace] = useState(false);
  const m = useMutation({ mutationFn: (body: object) => api<Answer>("/api/ask", { method: "POST", json: body }) });
  useEffect(() => {
    if (askOpen && askCtx.chart_id) {
      const question = `Explain the "${askCtx.title}" chart and what drives it.`;
      setQ(question);
      m.mutate({ question, context: askCtx, language: answerLang });
    } else if (askOpen && askCtx.question) setQ(askCtx.question);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [askOpen, askCtx]);
  if (!askOpen) return null;
  const role = me?.roles[0] ?? "executive";
  const suggestions = SUGGEST[role === "finance" ? "executive" : role === "investment_analyst" ? "cio" : role] ?? SUGGEST.executive;
  const submit = (question: string) => question.trim() && m.mutate({ question, context: askCtx.chart_id ? {} : askCtx, language: answerLang });
  const a = m.data;
  return (
    <aside className="fixed right-0 top-0 z-40 flex h-full w-full max-w-[460px] flex-col border-l border-line bg-side shadow-2xl" aria-label="Ask Flo">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2"><Bot className="h-5 w-5 text-gold" /><span className="font-semibold">{t("ask", lang)}</span>
          <Badge tone="neutral">mock model · deterministic</Badge></div>
        <Button size="icon" variant="ghost" onClick={closeAsk} aria-label="Close Ask Flo"><X className="h-4 w-4" /></Button>
      </div>
      <div className="flex-1 overflow-y-auto scroll-thin p-4 space-y-3">
        {!a && !m.isPending && (
          <div className="space-y-2">
            <p className="text-xs text-muted">Answers are computed by governed tools (deterministic analytics), checked for numeric grounding and filtered by your permissions.</p>
            {suggestions.map((s) => <button key={s} className="block w-full rounded-md border border-line px-3 py-2 text-left text-sm hover:border-gold" onClick={() => { setQ(s); if (!s.endsWith(" ")) submit(s); }}>{s}</button>)}
          </div>
        )}
        {m.isPending && <Spinner label="Agents working" />}
        {m.error && <ErrorState error={m.error} />}
        {a && (
          <div className="space-y-3">
            <div className="flex flex-wrap gap-1">
              <Badge tone="gold">{a.heading}</Badge><Badge tone="blue">route: {a.route}</Badge>
              {a.agents.map((x) => <Badge key={x}>{x.replace(/_agent$/, "")}</Badge>)}
              {a.injection?.flagged && <Badge tone="crit">prompt-injection flagged ({a.injection.severity})</Badge>}
            </div>
            {a.language_note && <p className="text-xs text-warn">{a.language_note}</p>}
            <div className="whitespace-pre-wrap text-sm leading-relaxed" data-testid="ask-answer">{a.text}</div>
            {a.warnings.length > 0 && <ul className="text-xs text-warn list-disc pl-4">{a.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
            {a.errors.length > 0 && <ul className="text-xs text-crit list-disc pl-4">{a.errors.map((e, i) => <li key={i}>{e.agent}: {e.failure_class} — {e.message}</li>)}</ul>}
            {a.citations.length > 0 && (
              <div><div className="mb-1 flex items-center gap-1 text-xs font-semibold"><BookOpen className="h-3.5 w-3.5" />Citations</div>
                <ol className="space-y-1 text-xs">{a.citations.map((c, i) => <li key={i}>[{i + 1}] {c.title} v{c.version} — {c.section} <span className="text-muted">({c.document_id})</span></li>)}</ol></div>
            )}
            {a.approvals.length > 0 && <div className="text-xs">Approvals: {a.approvals.map((x) => `${x.id} (${x.status})`).join(", ")}</div>}
            <button className="flex items-center gap-1 text-xs text-muted hover:text-ink" onClick={() => setShowTrace(!showTrace)} aria-expanded={showTrace}>
              <ShieldCheck className="h-3.5 w-3.5" />Governance trace ({a.tool_calls.length} tool calls, {a.policy_decisions.filter((p) => !p.allowed).length} denials)<ChevronDown className="h-3 w-3" />
            </button>
            {showTrace && (
              <div className="rounded-md border border-line p-2 text-[11px] space-y-1">
                <div>workflow {a.workflow_id} · {a.model_mode}</div>
                {a.tool_calls.map((tc, i) => <div key={i} className={tc.decision === "deny" ? "text-crit" : ""}>{tc.agent} → {tc.tool}: {tc.decision}{tc.rule ? ` (${tc.rule})` : ""}{tc.latency_ms != null ? ` · ${tc.latency_ms}ms` : ""}</div>)}
                <div className="text-muted">traces: {a.trace_ids.join(", ")}</div>
              </div>
            )}
          </div>
        )}
      </div>
      <form className="border-t border-line p-3 space-y-2" onSubmit={(e) => { e.preventDefault(); submit(q); }}>
        <textarea value={q} onChange={(e) => setQ(e.target.value)} rows={3} maxLength={4000} aria-label="Question for Flo"
          className="w-full rounded-md border border-line bg-bg p-2 text-sm" placeholder="Ask about AUM, portfolios, clients, policies…"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(q); }} />
        <div className="flex items-center justify-between gap-2">
          <Select value={answerLang} onChange={(e) => setAnswerLang(e.target.value as Lang)} aria-label="Answer language">
            {LANGS.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
          </Select>
          <Button variant="primary" type="submit" disabled={m.isPending}><Send className="h-4 w-4" />Ask</Button>
        </div>
      </form>
    </aside>
  );
}
