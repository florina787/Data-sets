import { useState } from "react";
import { useLocation } from "react-router-dom";
import { useApp } from "../../context";
import { openCopilot } from "../../screens/Copilot";
import { sectionFor } from "../Layout";

/** Page-specific questions Jerry can answer from available data (Amershi et al. G4). */
const SUGGESTIONS: Record<string, string[]> = {
  overview: ["Jerry, what changed since yesterday?", "What should I focus on before my board meeting?", "Are our AI systems healthy?"],
  priorities: ["What happened to the quality issue we discussed last week?", "What changed since yesterday?", "Is there enough apple stock for the Ontario weekend campaign?"],
  operations: ["Why are sales declining?", "Which products are running low in Vancouver?", "Which listings have allergen issues?"],
  network: ["Which suppliers are creating the most exposure?", "OriginTrace: summarise global supply chain risk and exposure", "What is the supply chain exposure in Peru?"],
  jerry: ["Give me a briefing", "What can you do?", "How did our sales do in the last 4 weeks?"],
  technology: ["Are our AI systems healthy?", "Which incidents are open?", "What happened in the checkout incident?"],
  reports: ["What changed since yesterday?", "Give me a briefing", "How did our sales do in the last 4 weeks?"],
};

export function JerryDock() {
  const { pathname } = useLocation();
  const { system } = useApp();
  const [open, setOpen] = useState(false);
  const key = sectionFor(pathname).key;
  if (key === "jerry") return null; // the full Jerry page already shows its own suggestions
  const live = system?.live_mode?.available;
  return (
    <div className="fixed bottom-4 right-4 z-30 flex flex-col items-end gap-2">
      {open && (
        <div className="w-80 rounded-2xl border border-surface-line bg-midnight/95 p-4 shadow-2xl backdrop-blur" role="dialog" aria-label="Ask Jerry about this page">
          <div className="eyebrow">Ask Jerry about this page</div>
          <p className="mt-1 text-xs text-ink-muted">I answer from cited, read-only data: sales, stock, compliance, inspections, the supply network,
            incidents, your decisions and system health. I say when the data can't answer, and I never take actions.</p>
          <p className="mt-1 text-[11px] text-ink-faint">{live ? "Local AI connected: answers are rewritten by your local model from the same cited facts." : "Rules-based mode: answers come straight from queries (local model not configured)."}</p>
          <ul className="mt-3 space-y-1.5">
            {SUGGESTIONS[key].map((q) => (
              <li key={q}><button className="w-full rounded-lg border border-surface-line bg-elevated/70 px-3 py-2 text-left text-sm text-ink hover:border-teal" onClick={() => { openCopilot(q); setOpen(false); }}>{q}</button></li>
            ))}
          </ul>
        </div>
      )}
      <button className="btn-primary rounded-full px-4 py-2 shadow-gold" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <span aria-hidden>✦</span> {open ? "Close" : "Jerry"}
      </button>
    </div>
  );
}
