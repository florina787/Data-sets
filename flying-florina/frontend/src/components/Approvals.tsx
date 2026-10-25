import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { get, post } from "@/lib/api";
import { datetime } from "@/lib/format";
import { Badge, Empty, ErrorBox, Loading, statusTone } from "./ui";

type Approval = {
  id: string; kind: string; title: string; requested_by: string; requested_at: string; expires_at: string; status: string; decided_by: string | null;
  payload_sha256: string; evidence_sha256: string | null; idempotency_key: string | null; executed: number; expired: boolean; risk: string;
  you_can_approve: boolean; you_can_execute: boolean; payload: Record<string, unknown>;
};

export function ApprovalQueue({ filterIds }: { filterIds?: string[] }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["approvals"], queryFn: () => get<Approval[]>("/api/approvals"), refetchInterval: 5000 });
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const act = useMutation({
    mutationFn: async ({ a, op }: { a: Approval; op: "approve" | "reject" | "execute" }) =>
      op === "execute" ? post(`/api/approvals/${a.id}/execute`, { idempotency_key: a.idempotency_key }) : post(`/api/approvals/${a.id}/${op}`, { note: "Decided in Flying_Florina UI" }),
    onSuccess: (r, v) => {
      setMsg({ ok: true, text: `${v.op} succeeded for ${v.a.id}${v.op === "execute" ? ` - ${JSON.stringify((r.data as { result: unknown }).result)}` : ""}` });
      qc.invalidateQueries({ queryKey: ["approvals"] });
    },
    onError: (e: Error & { details?: { policy_id?: string } }, v) => setMsg({ ok: false, text: `${v.op} denied: ${e.message}${e.details?.policy_id ? ` (${e.details.policy_id})` : ""}` }),
  });
  if (q.isLoading) return <Loading label="Loading approvals" />;
  if (q.error) return <ErrorBox error={q.error} onRetry={() => q.refetch()} />;
  const items = (q.data?.data ?? []).filter((a) => !filterIds || filterIds.includes(a.id));
  if (!items.length) return <Empty title="No approval requests">Run the AC-204 investigation from Mission Control to create a draft work order that needs approval.</Empty>;
  return (
    <div className="space-y-2" data-testid="approval-queue">
      {msg && (
        <div role="status" className={`rounded-lg border p-2 text-xs ${msg.ok ? "border-teal/40 bg-teal/10" : "border-blocked/40 bg-blocked/10"}`}>
          {msg.text}
        </div>
      )}
      {items.map((a) => (
        <div key={a.id} className="rounded-lg border border-token p-3 text-xs">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{a.title}</span>
            <Badge tone={statusTone(a.expired && a.status === "pending" ? "expired" : a.status)}>{a.expired && a.status === "pending" ? "expired" : a.status}</Badge>
            {a.executed ? <Badge tone="teal">executed (simulated)</Badge> : null}
            <Badge tone="gray">{a.kind}</Badge>
            <span className="muted ml-auto">{a.id}</span>
          </div>
          <div className="muted mt-1 grid gap-0.5 sm:grid-cols-2">
            <span>Requested by {a.requested_by} · {datetime(a.requested_at)}</span>
            <span>Expires {datetime(a.expires_at)}</span>
            <span className="truncate">Payload SHA-256 {a.payload_sha256.slice(0, 16)}...</span>
            {a.decided_by && <span>Decided by {a.decided_by} · evidence {a.evidence_sha256?.slice(0, 12)}...</span>}
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn btn-primary !py-1" disabled={a.status !== "pending" || act.isPending} onClick={() => act.mutate({ a, op: "approve" })} title={a.you_can_approve ? "" : "Policy will evaluate; separation of duties applies"}>
              Approve
            </button>
            <button className="btn btn-ghost !py-1" disabled={a.status !== "pending" || act.isPending} onClick={() => act.mutate({ a, op: "reject" })}>
              Reject
            </button>
            <button className="btn btn-ghost !py-1" disabled={a.status !== "approved" || act.isPending || !a.idempotency_key} onClick={() => act.mutate({ a, op: "execute" })}>
              {a.executed ? "Replay write (should be denied)" : "Execute approved write (simulated)"}
            </button>
          </div>
          {!a.you_can_approve && a.status === "pending" && <div className="muted mt-1">Tip: approvals require a different persona with an approver role (e.g. Reliability Engineer). The server enforces this.</div>}
        </div>
      ))}
    </div>
  );
}
