import { CheckCircle2, ChevronDown, Clock, Database, FileCheck2, Lock, ShieldX, XCircle } from "lucide-react";
import { useState } from "react";
import { Badge, cn } from "@/components/ui";
import type { AgentRun } from "../types";

const label = (a: string) => a.replace(/_agent$/, "").replace(/_/g, " ");

/** Expandable record of the governed agents behind one answer: what each is responsible for, what happened, measured
 * duration, the tools and data sources it used, evidence it contributed and the approvals its actions require.
 * No reasoning traces, tool arguments or record values are shown. */
export function AgentTimeline({ runs, latency }: { runs: AgentRun[]; latency?: number | null }) {
  const [open, setOpen] = useState(false);
  if (!runs.length) return null;
  const calls = runs.reduce((n, r) => n + r.tool_calls, 0);
  const ok = runs.filter((r) => r.status === "succeeded").length;
  return (
    <div className="rounded-xl border border-line/80 bg-bg/40">
      <button onClick={() => setOpen(!open)} aria-expanded={open} className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs">
        <span className="font-medium text-ink/90">Agent timeline</span>
        <span className="text-muted">{ok}/{runs.length} agents · {calls} governed tool calls{latency != null ? ` · ${latency} ms` : ""}</span>
        <ChevronDown className={cn("ml-auto h-3.5 w-3.5 text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ol className="relative space-y-3 border-t border-line/80 px-3 py-3">
          {runs.map((r) => {
            const good = r.status === "succeeded";
            const denied = r.status === "not_permitted" || r.status === "policy_denied";
            return (
              <li key={r.agent} className="relative pl-6 text-xs" data-agent-run={r.agent}>
                <span className="absolute left-0 top-0.5">
                  {good ? <CheckCircle2 className="h-4 w-4 text-pos" /> : denied ? <ShieldX className="h-4 w-4 text-warn" /> : <XCircle className="h-4 w-4 text-crit" />}
                </span>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="font-medium capitalize text-ink">{label(r.agent)}</span>
                  <Badge tone={good ? "good" : denied ? "warn" : "crit"}>{r.status.replace(/_/g, " ")}</Badge>
                  {r.duration_ms != null && <span className="flex items-center gap-0.5 text-muted"><Clock className="h-3 w-3" />{r.duration_ms} ms</span>}
                  {r.cached ? <span className="text-muted" title="Same user, roles, inputs, dataset and policy version: served from the harness cache">· cached result (verified earlier, same inputs)</span>
                    : <span className="text-muted">· {r.tool_calls} call{r.tool_calls === 1 ? "" : "s"}{r.denied_calls ? `, ${r.denied_calls} denied by policy` : ""}</span>}
                </div>
                <p className="mt-0.5 text-muted">{r.responsibility}</p>
                {(r.data_sources.length > 0 || r.evidence_refs > 0 || r.approval_actions.length > 0) && (
                  <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-muted">
                    {r.data_sources.length > 0 && <span className="flex items-center gap-1"><Database className="h-3 w-3" />{r.data_sources.join(" · ")}</span>}
                    {r.evidence_refs > 0 && <span className="flex items-center gap-1"><FileCheck2 className="h-3 w-3" />{r.evidence_refs} evidence reference{r.evidence_refs === 1 ? "" : "s"}</span>}
                    {r.approval_actions.length > 0 && <span className="flex items-center gap-1 text-warn"><Lock className="h-3 w-3" />approval: {r.approval_actions.join(", ")}</span>}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
