import { CheckCircle2, CircleDashed, Loader2, ShieldX, XCircle } from "lucide-react";
import { cn } from "@/components/ui";
import type { AgentEvent } from "../useConversation";
import type { Stage } from "../types";

const ORDER = ["understanding", "permissions", "evidence", "analysis", "visualization", "validation"];
const LABEL: Record<string, string> = { understanding: "Understanding request", permissions: "Checking permissions", evidence: "Retrieving evidence",
  analysis: "Running financial analysis", visualization: "Preparing visualizations", validation: "Validating recommendations" };

/** Renders only events the backend actually emitted; stages without an event stay pending. */
export function WorkflowProgress({ stages, agents, live, plan }: { stages: Stage[]; agents: AgentEvent[]; live: boolean;
  plan?: { supervisor: string; agents: string[]; skipped: string[] } }) {
  const latest: Record<string, Stage> = {};
  for (const s of stages) latest[s.id] = s;
  return (
    <div className="space-y-2" role="status" aria-live="polite" aria-label="Analysis progress">
      <ol className="space-y-1">
        {ORDER.map((id) => {
          const s = latest[id];
          const state: string = s?.status ?? "pending";
          return (
            <li key={id} className={cn("flex items-start gap-2 text-xs", state === "pending" ? "text-muted/60" : "text-ink/90")}>
              {state === "done" ? <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-pos" /> : state === "active" ?
                <Loader2 className={cn("mt-0.5 h-3.5 w-3.5 shrink-0 text-gold", live && "motion-safe:animate-spin")} /> : <CircleDashed className="mt-0.5 h-3.5 w-3.5 shrink-0" />}
              <span className="min-w-0">
                <span className="font-medium">{LABEL[id]}</span>
                {s?.detail && <span className="text-muted"> — {s.detail}</span>}
              </span>
              {s?.status === "done" && <span className="ml-auto shrink-0 tabular-nums text-[10px] text-muted">{s.t_ms} ms</span>}
            </li>
          );
        })}
      </ol>
      {(agents.length > 0 || plan) && (
        <ul className="flex flex-wrap gap-1" aria-label="Specialist agents">
          {plan?.skipped.map((a) => (
            <li key={`s-${a}`} className="flex items-center gap-1 rounded-full border border-warn/40 px-2 py-0.5 text-[11px] text-warn"><ShieldX className="h-3 w-3" />{a.replace(/_agent$/, "").replace(/_/g, " ")} · not permitted</li>
          ))}
          {agents.map((a, i) => (
            <li key={`${a.agent}-${i}`} title={a.tools?.join(", ")}
              className={cn("flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px]", a.status === "succeeded" ? "border-pos/40 text-pos" : "border-crit/40 text-crit")}>
              {a.status === "succeeded" ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
              {a.agent.replace(/_agent$/, "").replace(/_/g, " ")}{a.tools?.length ? ` · ${a.tools.length} tool call${a.tools.length > 1 ? "s" : ""}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
