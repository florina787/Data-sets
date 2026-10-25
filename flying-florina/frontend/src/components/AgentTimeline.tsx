import { CheckCircle2, CircleDashed, Loader2, RotateCcw, SkipForward, XCircle, Ban, PauseCircle } from "lucide-react";
import { time } from "@/lib/format";
import type { WorkflowEvent } from "@/lib/types";
import { Badge, statusTone } from "./ui";

const ICON: Record<string, typeof CheckCircle2> = {
  completed: CheckCircle2, running: Loader2, queued: CircleDashed, retrying: RotateCcw, failed: XCircle, skipped: SkipForward, cancelled: Ban, halted: PauseCircle, started: CircleDashed,
};

/** Real execution log: one row per persisted event, with its own timestamp. Nothing here is animated or invented. */
export function AgentTimeline({ events, compact = false }: { events: WorkflowEvent[]; compact?: boolean }) {
  const shown = compact ? events.filter((e) => !["queued", "running"].includes(e.status) || e === events[events.length - 1]) : events;
  return (
    <ol className="space-y-1.5" aria-label="Agent execution timeline" data-testid="timeline">
      {shown.map((e) => {
        const Icon = ICON[e.status] ?? CircleDashed;
        const tone = statusTone(e.status === "halted" ? "denied" : e.status);
        const tools = (e.detail?.tools as string[] | undefined) ?? [];
        return (
          <li key={e.id} className="flex items-start gap-2 text-xs">
            <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${tone === "teal" ? "text-teal" : tone === "red" ? "text-blocked" : tone === "amber" ? "text-amber" : "muted"} ${e.status === "running" ? "animate-spin" : ""}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="font-semibold">{e.step}</span>
                <span className="muted">· {e.agent}</span>
                <Badge tone={tone}>{e.status}</Badge>
                {e.attempt > 1 && <Badge tone="amber">attempt {e.attempt}</Badge>}
                {e.duration_ms != null && <span className="muted tabular-nums">{e.duration_ms.toFixed(0)} ms</span>}
                <span className="muted ml-auto tabular-nums">{time(e.ts)}</span>
              </div>
              {e.summary && !compact && <div className="muted mt-0.5 break-words">{e.summary}</div>}
              {e.summary && compact && e.status !== "queued" && <div className="muted mt-0.5 line-clamp-2 break-words">{e.summary}</div>}
              {tools.length > 0 && (
                <div className="mt-0.5 flex flex-wrap gap-1">
                  {tools.map((t) => (
                    <code key={t} className="rounded bg-[var(--panel-2)] px-1 text-[10px]">
                      {t}
                    </code>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
