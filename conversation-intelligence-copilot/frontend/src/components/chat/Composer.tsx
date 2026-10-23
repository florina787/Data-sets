import { ArrowUp, BrainCircuit, Calculator, Sparkles, Square } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { useApp } from "@/app/AppState";
import { Tip } from "@/components/common/ui";
import { cn } from "@/lib/utils";
import type { AnalysisMode } from "@/types/api";

const MODES: { id: AnalysisMode; label: string; icon: typeof Sparkles; tip: string }[] = [
  { id: "auto", label: "Auto", icon: Sparkles, tip: "Uses a model only when the question needs interpretation or the rules cannot route it. The answer says which route it took and why." },
  { id: "analytics_only", label: "Analytics only", icon: Calculator, tip: "Never calls a model: registered DuckDB operations, FAISS evidence and deterministic narratives. Zero tokens." },
  { id: "hybrid_ai", label: "Hybrid AI", icon: BrainCircuit, tip: "The model interprets the question when rules are unsure and explains the verified results. Facts still come from DuckDB." },
];

export function ModeSwitch() {
  const { analysisMode, setAnalysisMode, model } = useApp();
  return (
    <div role="radiogroup" aria-label="Analysis mode" className="flex items-center gap-0.5 rounded-xl border border-line bg-white/[0.02] p-0.5">
      {MODES.map(({ id, label, icon: Icon, tip }) => (
        <Tip key={id} content={id === "hybrid_ai" && model && !model.available ? `${tip} No model is available right now, so this falls back to analytics only.` : tip}>
          <button role="radio" aria-checked={analysisMode === id} onClick={() => setAnalysisMode(id)} data-testid={`mode-${id}`}
            className={cn("focus-ring flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] font-medium transition",
              analysisMode === id ? "bg-indigo/20 text-ink" : "text-faint hover:text-ink")}>
            <Icon className="h-3 w-3" aria-hidden />{label}
          </button>
        </Tip>
      ))}
    </div>
  );
}

export function Composer({ large = false, autoFocus = false }: { large?: boolean; autoFocus?: boolean }) {
  const { ask, busy, cancel, selectedConversation, setSelectedConversation } = useApp();
  const [value, setValue] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => { if (autoFocus) ref.current?.focus(); }, [autoFocus]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);
  const submit = () => {
    if (!value.trim() || busy) return;
    ask(value);
    setValue("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };
  return (
    <div className={cn("group relative rounded-2xl p-[1px] transition-shadow", large ? "bg-gradient-to-r from-indigo/60 via-violet/40 to-cyan/60 shadow-glow" : "bg-line")}>
      <div className="rounded-2xl bg-surface/95 backdrop-blur-xl">
        {selectedConversation && (
          <div className="flex items-center gap-2 px-4 pt-3 text-xs text-muted">
            <span className="rounded-md bg-violet/15 px-2 py-0.5 font-mono text-violet">{selectedConversation}</span> selected for conversation questions
            <button className="focus-ring rounded text-faint hover:text-ink" onClick={() => setSelectedConversation(null)} aria-label="Clear selected conversation">clear</button>
          </div>
        )}
        <div className="flex items-center justify-between gap-2 px-3 pt-2.5">
          <ModeSwitch />
        </div>
        <div className="flex items-end gap-2 p-2.5 pt-1">
          <label htmlFor="composer" className="sr-only">Ask a question about the customer conversations</label>
          <textarea id="composer" ref={ref} rows={1} value={value} onChange={(e) => setValue(e.target.value)} onKeyDown={onKey} maxLength={1000}
            placeholder="Ask about sentiment, topics, agents, a conversation, or what leadership should review…"
            className={cn("max-h-[200px] flex-1 resize-none bg-transparent px-2.5 py-2 text-ink placeholder:text-faint focus:outline-none", large ? "text-base" : "text-sm")} />
          {busy ? (
            <button onClick={cancel} className="focus-ring grid h-10 w-10 place-items-center rounded-xl border border-line bg-elevated text-ink hover:bg-white/10" aria-label="Stop analysis">
              <Square className="h-4 w-4" />
            </button>
          ) : (
            <button onClick={submit} disabled={!value.trim()} className="focus-ring grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-indigo to-violet text-white shadow-glow transition disabled:opacity-40 disabled:shadow-none" aria-label="Send question">
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
