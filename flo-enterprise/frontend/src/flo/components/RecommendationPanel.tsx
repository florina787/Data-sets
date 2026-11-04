import { ChevronDown, FileCheck2, ShieldCheck, UserCheck } from "lucide-react";
import { useState } from "react";
import { Badge, cn } from "@/components/ui";
import type { Recommendation } from "../types";

const PTONE = { P1: "crit", P2: "warn", P3: "blue" } as const;

function Rec({ r, onAsk, open, toggle }: { r: Recommendation; onAsk: (q: string) => void; open: boolean; toggle: () => void }) {
  return (
    <li className="rounded-xl border border-line bg-card" data-rec={r.id}>
      <button onClick={toggle} aria-expanded={open} className="flex w-full items-start gap-3 p-3.5 text-left">
        <Badge tone={PTONE[r.priority]} className="mt-0.5">{r.priority}</Badge>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium leading-snug">{r.title}</div>
          <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] text-muted">
            <span>{r.owner_function}</span><span>{r.timeframe}</span><span>complexity: {r.complexity}</span>
            {r.approvals_required.length > 0 && <span className="text-warn">approval-gated</span>}
          </div>
        </div>
        <ChevronDown className={cn("h-4 w-4 shrink-0 text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-2.5 border-t border-line px-3.5 pb-3.5 pt-3 text-xs">
          <p><span className="font-semibold">Why: </span>{r.rationale}</p>
          <p><span className="font-semibold">Expected benefit: </span>{r.expected_benefit} <span className="text-muted">(described, not estimated)</span></p>
          {r.kpis.length > 0 && <p className="flex flex-wrap items-center gap-1"><span className="font-semibold">KPIs to track:</span>{r.kpis.map((k) => <Badge key={k}>{k}</Badge>)}</p>}
          {r.dependencies.length > 0 && <p><span className="font-semibold">Dependencies: </span>{r.dependencies.join("; ")}</p>}
          {r.validation_criteria.length > 0 && (
            <div><span className="font-semibold">Validation criteria</span>
              <ul className="mt-0.5 list-disc pl-4">{r.validation_criteria.map((v) => <li key={v}>{v}</li>)}</ul></div>
          )}
          {r.approvals_required.length > 0 && (
            <p className="flex items-start gap-1 text-warn"><ShieldCheck className="mt-0.5 h-3.5 w-3.5" />{r.approvals_required.join(" · ")}</p>
          )}
          {r.requires_human_review && <p className="flex items-center gap-1 text-muted"><UserCheck className="h-3.5 w-3.5" />Requires an authorized human decision before any action.</p>}
          <div>
            <span className="flex items-center gap-1 font-semibold"><FileCheck2 className="h-3.5 w-3.5" />Evidence</span>
            <ul className="mt-1 space-y-0.5 text-muted">
              {r.evidence.map((e, i) => <li key={i}><code className="text-ink/80">{e.agent}.{e.fact}</code>{e.value && <> = {e.value}</>}{e.tool && <> · via {e.tool}</>}</li>)}
            </ul>
          </div>
          <button onClick={() => onAsk(`Explain recommendation "${r.title}" and how to implement it.`)} className="text-gold hover:underline">Ask FLO how to implement this →</button>
        </div>
      )}
    </li>
  );
}

export function RecommendationPanel({ recs, onAsk }: { recs: Recommendation[]; onAsk: (q: string) => void }) {
  const [open, setOpen] = useState<string | null>(recs[0]?.id ?? null);
  if (!recs.length) return null;
  return (
    <section aria-label="Recommendations" className="space-y-2">
      <h3 className="text-sm font-semibold">Prioritized recommendations</h3>
      <ul className="space-y-2">{recs.map((r) => <Rec key={r.id} r={r} onAsk={onAsk} open={open === r.id} toggle={() => setOpen(open === r.id ? null : r.id)} />)}</ul>
      <p className="text-[11px] text-muted">Every recommendation cites the governed facts it rests on. FLO does not estimate ROI, probabilities or returns; personalized advice needs approved rules and human review.</p>
    </section>
  );
}
