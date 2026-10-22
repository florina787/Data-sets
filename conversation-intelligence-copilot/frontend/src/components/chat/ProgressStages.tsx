import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, XCircle } from "lucide-react";
import type { Turn } from "@/app/AppState";
import { ms } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Shows the graph nodes as they actually start and finish (from SSE events). No timers. */
export function ProgressStages({ turn, compact }: { turn: Turn; compact?: boolean }) {
  const running = turn.order.find((n) => turn.nodes[n]?.status === "running");
  return (
    <div className="space-y-2" aria-live="polite">
      {!compact && (
        <p className="text-xs text-muted">
          {turn.status === "streaming" ? <>Running <span className="text-cyan">{running ? turn.nodes[running].label : "workflow"}</span>…</> : "Workflow"}
          <span className="text-faint"> · {turn.order.length} steps</span>
        </p>
      )}
      <ol className="flex flex-wrap gap-1.5">
        <AnimatePresence initial={false}>
          {turn.order.map((n) => {
            const s = turn.nodes[n];
            return (
              <motion.li key={n} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.2 }}
                className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
                  s.status === "running" ? "border-cyan/50 bg-cyan/10 text-ink" : s.status === "failed" ? "border-neg/40 bg-neg/10 text-ink"
                    : s.status === "skipped" ? "border-line text-faint" : "border-line bg-white/[0.03] text-muted")}
                title={s.error ?? (s.summary ? JSON.stringify(s.summary).slice(0, 300) : undefined)}>
                {s.status === "running" ? <Loader2 className="h-3 w-3 animate-spin text-cyan" /> : s.status === "failed" ? <XCircle className="h-3 w-3 text-neg" />
                  : <CheckCircle2 className="h-3 w-3 text-pos" />}
                <span>{s.label ?? n}</span>
                {s.duration_ms !== undefined && <span className="num text-faint">{ms(s.duration_ms)}</span>}
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
    </div>
  );
}
