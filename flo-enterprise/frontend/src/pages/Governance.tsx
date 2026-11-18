import { useMutation, useQuery } from "@tanstack/react-query";
import { createColumnHelper } from "@tanstack/react-table";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { Badge, Button, Card, ErrorState, Input, Label, PageHeader, Spinner, Stat, Tabs } from "@/components/ui";
import { api } from "@/lib/api";

const ch = createColumnHelper<any>();
type Tab = "status" | "audit" | "policies" | "check";

export default function Governance() {
  const [tab, setTab] = useState<Tab>("status");
  return (
    <div className="space-y-4">
      <PageHeader title="Governance & Audit" subtitle="Independent enforcement plane: deny-by-default policy-as-code (OPA-parity tested), hash-chained audit log, approval rules." />
      <Tabs value={tab} onChange={setTab} tabs={[{ id: "status", label: "Status" }, { id: "audit", label: "Audit log" }, { id: "policies", label: "Policies (RBAC/ABAC)" }, { id: "check", label: "Authorization explainer" }]} />
      {tab === "status" && <Status />}{tab === "audit" && <Audit />}{tab === "policies" && <Policies />}{tab === "check" && <Check />}
    </div>
  );
}

function Status() {
  const q = useQuery({ queryKey: ["gov"], queryFn: () => api("/api/governance/status") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const s = q.data;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      <Stat label="Policy version" value={<span className="text-base">{s.policy_version}</span>} sub={s.pdp} />
      <Stat label="Audit chain" value={typeof s.audit_chain === "object" ? (s.audit_chain.valid ? "Valid" : "BROKEN") : "—"} tone={s.audit_chain?.valid ? "good" : "crit"} sub={typeof s.audit_chain === "object" ? `${s.audit_chain.events_checked} events` : s.audit_chain} />
      <Stat label="Model provider" value={<span className="text-base">{s.model_provider}</span>} /><Stat label="Observability" value={s.observability} />
      <Stat label="Identity provider" value={<span className="text-base">{s.identity_provider}</span>} /><Stat label="Integrations" value={<span className="text-base">mock adapters</span>} sub={s.integrations} />
      <Stat label="Trading" value={s.trading} tone="good" /><Stat label="Data" value={s.data} sub={`Presidio installed: ${s.presidio}`} />
    </div>
  );
}

function Audit() {
  const [f, setF] = useState({ action: "", decision: "" });
  const q = useQuery({ queryKey: ["audit", f], queryFn: () => api(`/api/audit/events?limit=500${f.action ? `&action=${f.action}` : ""}${f.decision ? `&decision=${f.decision}` : ""}`) });
  const v = useMutation({ mutationFn: () => api("/api/audit/verify") });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2"><div><Label>Action prefix</Label><Input value={f.action} onChange={(e) => setF({ ...f, action: e.target.value })} placeholder="tool.invoke" /></div>
        <div><Label>Decision</Label><Input value={f.decision} onChange={(e) => setF({ ...f, decision: e.target.value })} placeholder="deny" /></div>
        <Button onClick={() => v.mutate()}>Verify hash chain</Button>{v.data && <Badge tone={v.data.valid ? "good" : "crit"}>{v.data.valid ? `valid · ${v.data.events_checked} events` : `broken at seq ${v.data.first_invalid_seq}`}</Badge>}</div>
      {q.isLoading ? <Spinner /> : q.error ? <ErrorState error={q.error} /> : <DataTable label="Audit events" data={q.data.events} columns={[ch.accessor("seq", { header: "#" }), ch.accessor("ts", { header: "Time", cell: (c) => c.getValue().slice(0, 19) }),
        ch.accessor("actor", { header: "Actor" }), ch.accessor("action", { header: "Action" }), ch.accessor("resource_id", { header: "Resource" }),
        ch.accessor("decision", { header: "Decision", cell: (c) => <Badge tone={c.getValue() === "deny" ? "crit" : c.getValue() === "allow" ? "good" : "neutral"}>{c.getValue()}</Badge> }),
        ch.accessor("reasons", { header: "Rules", cell: (c) => (c.getValue() || []).map((r: any) => r.rule).filter(Boolean).join(", ") }), ch.accessor("hash", { header: "Hash" })]} />}
    </div>
  );
}

function Policies() {
  const q = useQuery({ queryKey: ["policies"], queryFn: () => api("/api/governance/policies") });
  if (q.isLoading) return <Spinner />;
  if (q.error) return <ErrorState error={q.error} />;
  const roles = Object.keys(q.data.rbac.roles);
  const perms = Array.from(new Set(roles.flatMap((r) => q.data.rbac.roles[r]))).sort() as string[];
  return (
    <div className="space-y-4">
      <Card className="overflow-auto scroll-thin p-4"><h3 className="mb-2 text-sm font-semibold">RBAC matrix ({q.data.version})</h3>
        <table className="text-[11px]"><thead><tr><th className="text-left pr-2">permission</th>{roles.map((r) => <th key={r} className="px-1 text-muted">{r}</th>)}</tr></thead>
          <tbody>{perms.map((p) => <tr key={p} className="border-t border-line/50"><td className="pr-2">{p}</td>{roles.map((r) => <td key={r} className="text-center">{q.data.rbac.roles[r].includes(p) ? "●" : ""}</td>)}</tr>)}</tbody></table>
        <p className="mt-2 text-xs">Prohibited for everyone: {q.data.rbac.prohibited.join(", ")}</p></Card>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">ABAC rules</h3>{q.data.abac.rules.map((r: any) => <div key={r.id} className="mb-2 text-xs"><b className="text-gold">{r.id}</b> — {r.description}<div className="text-muted">actions: {r.actions.join(", ")}{r.resource_types ? ` · resources: ${r.resource_types.join(", ")}` : ""}</div></div>)}</Card>
      <Card className="p-4"><h3 className="mb-2 text-sm font-semibold">Approval rules</h3><pre className="text-[11px]">{JSON.stringify(q.data.approvals, null, 2)}</pre></Card>
    </div>
  );
}

function Check() {
  const [b, setB] = useState({ action: "client:read", resource_ref: "client:C-00001", purpose: "" });
  const m = useMutation({ mutationFn: () => api("/api/governance/check", { method: "POST", json: { ...b, purpose: b.purpose || null } }) });
  return (
    <Card className="space-y-3 p-4"><p className="text-xs text-muted">Explains decisions for your own identity only.</p>
      <div className="grid gap-2 md:grid-cols-3">{(["action", "resource_ref", "purpose"] as const).map((k) => <div key={k}><Label>{k}</Label><Input value={b[k]} onChange={(e) => setB({ ...b, [k]: e.target.value })} /></div>)}</div>
      <Button variant="primary" onClick={() => m.mutate()}>Evaluate</Button>
      {m.error && <ErrorState error={m.error} />}
      {m.data && <div className="text-sm"><Badge tone={m.data.allowed ? "good" : "crit"}>{m.data.allowed ? "ALLOW" : "DENY"}</Badge> <span className="text-xs text-muted">{m.data.policy_version}</span>
        <ul className="mt-2 text-xs">{m.data.reasons.map((r: any, i: number) => <li key={i} className={r.effect === "deny" ? "text-crit" : ""}>{r.rule}: {r.message}</li>)}</ul>
        {m.data.obligations.length > 0 && <div className="text-xs text-warn">Obligations: {m.data.obligations.join(", ")}</div>}</div>}
    </Card>
  );
}
