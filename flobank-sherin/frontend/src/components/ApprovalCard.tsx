import { useState } from "react";
import { Ban, Check, MessageSquareWarning, ShieldAlert, TrendingUp } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/store";
import { money } from "../lib/format";
import { Badge, StatusBadge } from "./ui";

export interface ApprovalT {
  id: string; kind: string; title: string; summary: string; status: string; requested_by: string; required_roles: string[]; outstanding_roles: string[];
  financial_impact_usd: number; risk_evidence: string[]; policy_blocked: boolean; can_be_approved: boolean; decisions: any[]; data_class: string;
}

export function ApprovalCard({ a, onChange, compact = false }: { a: ApprovalT; onChange?: (a: ApprovalT) => void; compact?: boolean }) {
  const { role, user } = useApp();
  const [comment, setComment] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const decide = async (decision: string) => {
    setBusy(true); setErr(null);
    try { const r = await api<ApprovalT>(`/approvals/${a.id}/decision`, { method: "POST", body: { decision, comment } }); onChange?.(r); setComment(""); }
    catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const final = ["approved", "rejected"].includes(a.status);
  const canApproveAsRole = a.outstanding_roles.includes(role);
  return (
    <article data-testid={`approval-${a.id}`} className={`rounded-2xl border ${a.policy_blocked ? "border-[#EFC9C6] bg-red-light/40" : "border-line bg-white"} p-3.5 text-sm shadow-sm`}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5"><Badge tone="dark">{a.kind.replace("_", " ")}</Badge><StatusBadge s={a.status} />{a.data_class === "synthetic" && <Badge tone="gold">synthetic</Badge>}</div>
          <h3 className="mt-1 font-semibold text-flo-950">{a.title}</h3>
          <p className="text-xs text-muted">{a.id} · requested by {a.requested_by}</p>
        </div>
        {a.financial_impact_usd > 0 && <div className="text-right"><div className="text-[10px] uppercase tracking-wide text-muted">Financial exposure</div>
          <div className="flex items-center gap-1 font-display text-lg font-semibold text-flo-900"><TrendingUp className="h-4 w-4" aria-hidden />{money(a.financial_impact_usd, "USD")}</div></div>}
      </header>
      {!compact && <p className="mt-1.5 text-[13px] text-ink/80">{a.summary}</p>}
      {a.risk_evidence?.length > 0 && <ul className="mt-2 space-y-0.5 text-xs text-muted">{a.risk_evidence.slice(0, compact ? 3 : 10).map((e, i) => <li key={i}>• {e}</li>)}</ul>}
      <div className="mt-2 flex flex-wrap items-center gap-1 text-[11px]">
        <span className="text-muted">Requires:</span>{a.required_roles.map((r) => <Badge key={r} tone={a.outstanding_roles.includes(r) ? "amber" : "green"}>{r.replace(/_/g, " ")}</Badge>)}
      </div>
      {a.policy_blocked && <p className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-red"><ShieldAlert className="h-4 w-4" />Mandatory policy block. No role can approve this request.</p>}
      {a.decisions?.length > 0 && <ol className="mt-2 space-y-0.5 text-[11px] text-muted">{a.decisions.map((d, i) => <li key={i}>{d.at} · {d.actor} ({d.role}) → <strong>{d.decision}</strong>{d.comment && `: “${d.comment}”`}</li>)}</ol>}
      {!final && a.status !== "blocked" && a.status !== "insufficient_data" && (
        <div className="mt-3 space-y-2">
          <input aria-label="Decision comment" value={comment} onChange={(e) => setComment(e.target.value)} placeholder={`Comment as ${user} (${role.replace(/_/g, " ")})`}
            className="w-full rounded-xl border border-line px-3 py-1.5 text-xs" />
          <div className="flex flex-wrap gap-1.5">
            <button type="button" disabled={busy || !a.can_be_approved || !canApproveAsRole} title={!canApproveAsRole ? `Your role (${role.replace(/_/g, " ")}) is not an outstanding approver` : undefined} onClick={() => decide("approve")} className="inline-flex items-center gap-1 rounded-full bg-flo-800 px-3 py-1 text-xs font-semibold text-white disabled:opacity-40"><Check className="h-3.5 w-3.5" />Approve</button>
            <button type="button" disabled={busy} onClick={() => decide("reject")} className="inline-flex items-center gap-1 rounded-full bg-red px-3 py-1 text-xs font-semibold text-white disabled:opacity-40"><Ban className="h-3.5 w-3.5" />Reject</button>
            <button type="button" disabled={busy} onClick={() => decide("request_changes")} className="rounded-full border border-line px-3 py-1 text-xs font-semibold text-flo-900">Request changes</button>
            <button type="button" disabled={busy} onClick={() => decide("escalate")} className="inline-flex items-center gap-1 rounded-full border border-line px-3 py-1 text-xs font-semibold text-amber"><MessageSquareWarning className="h-3.5 w-3.5" />Escalate</button>
          </div>
        </div>
      )}
      {!final && a.can_be_approved && !canApproveAsRole && <p className="mt-1.5 text-[11px] text-muted">Approval needs: {a.outstanding_roles.map((r) => r.replace(/_/g, " ")).join(", ")}. The server enforces this independently.</p>}
      {err && <p role="alert" className="mt-2 rounded-lg bg-red-light px-2 py-1 text-xs text-red">{err}</p>}
    </article>
  );
}
