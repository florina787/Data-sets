import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Play, X } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";

const TONE: Record<string, any> = { pending: "warn", approved: "blue", executed: "good", rejected: "crit", expired: "neutral", invalidated: "crit" };

export default function Approvals() {
  const { me } = useApp();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [sel, setSel] = useState<any>(null);
  const [note, setNote] = useState("");
  const list = useQuery({ queryKey: ["approvals", status], queryFn: () => api(`/api/approvals${status ? `?status=${status}` : ""}`) });
  const done = () => { qc.invalidateQueries({ queryKey: ["approvals"] }); setSel(null); };
  const decide = useMutation({ mutationFn: (approve: boolean) => api(`/api/approvals/${sel.id}/decide`, { method: "POST", json: { approve, payload_hash: sel.payload_hash, note } }), onSuccess: done });
  const exec = useMutation({ mutationFn: () => api(`/api/approvals/${sel.id}/execute`, { method: "POST", json: { payload: sel.payload } }), onSuccess: done });
  const isApprover = sel && me && me.roles.some((r) => sel.approver_role.split(",").includes(r)) && sel.requested_by !== me.user_id;
  return (
    <div className="space-y-4">
      <PageHeader title="Approvals" subtitle="Durable human-in-the-loop control. Approvers review the exact payload; its SHA-256 hash is bound to the decision. Self-approval, replay and post-approval edits are blocked."
        actions={<Select aria-label="Status filter" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option>{Object.keys(TONE).map((s) => <option key={s}>{s}</option>)}</Select>} />
      <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr]">
        <Card className="p-2">
          {list.isLoading ? <Spinner /> : list.error ? <ErrorState error={list.error} /> : list.data.approvals.length === 0 ? <p className="p-3 text-sm text-muted">No approvals visible to you.</p> :
            <ul className="divide-y divide-line">{list.data.approvals.map((a: any) => (
              <li key={a.id}><button className={`w-full p-3 text-left hover:bg-line/30 ${sel?.id === a.id ? "bg-line/30" : ""}`} onClick={() => setSel(a)}>
                <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">{a.action_type}</span><Badge tone={TONE[a.status]}>{a.status}</Badge></div>
                <div className="text-xs text-muted">{a.id} · {a.resource_ref} · requested by {a.requested_by} · {a.created_at.slice(0, 16)} · risk {a.risk_class}</div>
              </button></li>))}</ul>}
        </Card>
        {sel ? (
          <Card className="space-y-3 p-4">
            <div className="flex flex-wrap items-center gap-2"><h2 className="font-semibold">{sel.id}</h2><Badge tone={TONE[sel.status]}>{sel.status}</Badge><Badge tone="crit">risk {sel.risk_class}</Badge></div>
            <dl className="grid grid-cols-[140px_1fr] gap-1 text-xs">
              <dt className="text-muted">Action type</dt><dd>{sel.action_type}</dd><dt className="text-muted">Requesting identity</dt><dd>{sel.requested_by}</dd>
              <dt className="text-muted">Resource</dt><dd>{sel.resource_ref}</dd><dt className="text-muted">Authorized approver</dt><dd>{sel.approver_role}</dd>
              <dt className="text-muted">Payload hash</dt><dd className="font-mono break-all">{sel.payload_hash}</dd><dt className="text-muted">Expires</dt><dd>{sel.expires_at}</dd>
              <dt className="text-muted">Policy version</dt><dd>{sel.policy_version}</dd>{sel.decided_by && <><dt className="text-muted">Decided by</dt><dd>{sel.decided_by} · {sel.decision_note}</dd></>}
            </dl>
            <div><div className="mb-1 text-xs font-semibold">Exact proposed payload</div>
              <pre className="max-h-72 overflow-auto scroll-thin whitespace-pre-wrap rounded-md border border-line bg-bg p-3 text-xs">{typeof sel.payload.body === "string" ? `Subject: ${sel.payload.subject}\n\n${sel.payload.body}` : JSON.stringify(sel.payload, null, 2)}</pre></div>
            <div><div className="mb-1 text-xs font-semibold">Supporting evidence</div><pre className="max-h-40 overflow-auto scroll-thin rounded-md border border-line bg-bg p-2 text-[11px]">{JSON.stringify(sel.evidence, null, 2)}</pre></div>
            {sel.status === "pending" && isApprover && (
              <div className="space-y-2"><Input placeholder="Decision note" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Decision note" />
                <div className="flex gap-2"><Button variant="primary" onClick={() => decide.mutate(true)}><Check className="h-4 w-4" />Approve this exact payload</Button>
                  <Button variant="danger" onClick={() => decide.mutate(false)}><X className="h-4 w-4" />Reject</Button></div></div>
            )}
            {sel.status === "approved" && sel.requested_by === me?.user_id && sel.action_type !== "comms:send" && <Button variant="blue" onClick={() => exec.mutate()}><Play className="h-4 w-4" />Execute (re-authorizes first)</Button>}
            {sel.status === "approved" && sel.action_type === "comms:send" && <p className="text-xs text-muted">Client communications are sent from the client's Communication drafting tab, which resumes the durable workflow.</p>}
            {sel.execution_result && <pre className="rounded-md border border-line bg-bg p-2 text-[11px]">{JSON.stringify(sel.execution_result, null, 2)}</pre>}
            {(decide.error || exec.error) && <ErrorState error={decide.error || exec.error} />}
          </Card>
        ) : <Card className="p-6 text-sm text-muted">Select an approval to review its exact payload, evidence and hash.</Card>}
      </div>
    </div>
  );
}
