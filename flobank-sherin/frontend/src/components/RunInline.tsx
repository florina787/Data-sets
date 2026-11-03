import { useApi } from "../lib/api";
import { ApprovalCard } from "./ApprovalCard";
import { DiffView, StatusBadge } from "./ui";
import { CheckCircle2, CircleDashed, Loader2, XCircle } from "lucide-react";

/** Live view of a harness run inside chat: steps, verification, diff, and the approval card when paused. */
export function RunInline({ runId }: { runId: string }) {
  const run = useApi<any>(`/harness/runs/${runId}`, undefined, 1500);
  const r = run.data;
  const approvalId = r?.result?.approval_id;
  // Refetch whenever the run changes state so the card never shows a stale decision.
  const ap = useApi<any>(approvalId ? `/approvals/${approvalId}` : null, { run_status: r?.status }, r?.status === "awaiting_approval" ? 3000 : undefined);
  if (!r) return null;
  const steps = r.result?.steps ?? [];
  const diff = steps.map((s: any) => s.output?.diff).find(Boolean);
  return (
    <div className="mt-2 rounded-xl border border-line bg-flo-50/60 p-2.5 text-xs" data-testid="run-inline">
      <div className="mb-1 flex items-center justify-between"><span className="font-semibold text-flo-900">Agent run {r.id}</span><StatusBadge s={r.status} /></div>
      <ol className="space-y-0.5">
        {r.plan.map((p: any) => {
          const st = steps.find((s: any) => s.step === p.step);
          return <li key={p.step} className="flex items-center gap-1.5 [&>svg]:shrink-0">
            {!st ? (r.status === "running" ? <Loader2 className="h-3.5 w-3.5 animate-spin text-flo-700" /> : <CircleDashed className="h-3.5 w-3.5 text-muted" />) : st.ok ? <CheckCircle2 className="h-3.5 w-3.5 text-flo-700" /> : <XCircle className="h-3.5 w-3.5 text-red" />}
            <span className="font-semibold">{p.agent.replace(/_/g, " ")}</span> <code className="text-flo-800">{p.tool}</code> <span className="text-muted">{p.objective}</span>
            {st?.output?.findings && <span className="text-muted">· {st.output.findings.length} finding(s)</span>}
          </li>;
        })}
      </ol>
      {diff && <div className="mt-2"><DiffView diff={diff} /></div>}
      {ap.data && <div className="mt-2"><ApprovalCard a={ap.data} compact onChange={() => { ap.reload(); run.reload(); }} /></div>}
      {r.result?.sentence && <p className="mt-2 rounded-lg bg-white p-2 text-[12px] text-flo-900">{r.result.sentence}</p>}
    </div>
  );
}
