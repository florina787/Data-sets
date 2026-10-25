import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Download, Play, Power, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ApprovalQueue } from "@/components/Approvals";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHeader, Tabs } from "@/components/ui";
import { DecisionList } from "@/components/Workspace";
import { download, post } from "@/lib/api";
import { datetime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Decision } from "@/lib/types";

const TABS = [
  { id: "policies", label: "Policy Library" }, { id: "trace", label: "Live Decision Trace" }, { id: "classification", label: "Data Classification" },
  { id: "tools", label: "MCP Tool Permissions" }, { id: "approvals", label: "Approval Queue" }, { id: "ledger", label: "Evidence Ledger" },
  { id: "compliance", label: "Compliance Matrix" }, { id: "lab", label: "Security Test Lab" }, { id: "incident", label: "Incident / Kill Switch" }, { id: "export", label: "Audit Export" },
];

type Catalog = { version: string; policies: Record<string, unknown>[]; role_actions: Record<string, string[]>; approver_roles: Record<string, string[]> };
type LabRow = { id: string; title: string; expected: string; observed: string; passed: boolean; policy_id: string; reason: string; ts: string; tool_invocations: number; detail?: string };
type AuditEv = { seq: number; id: string; ts: string; actor: string; kind: string; summary: string; hash: string; prev_hash: string };

export function TrustPage() {
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") ?? "policies");
  return (
    <div className="space-y-4">
      <PageHeader title="Defense Trust Center" subtitle="Policy-as-code, deny by default. Decisions are deterministic Python; no model decides what is allowed." icon={<ShieldCheck className="h-5 w-5" />} />
      <Tabs label="Trust Center sections" tabs={TABS} active={tab} onChange={setTab} />
      {tab === "policies" && <Policies />}
      {tab === "trace" && <Trace />}
      {tab === "classification" && <Classification />}
      {tab === "tools" && <ToolPerms />}
      {tab === "approvals" && <Card title="Approval queue" subtitle="Separation of duties, expiry, signed evidence hash, execution-time policy check and replay protection."><ApprovalQueue /></Card>}
      {tab === "ledger" && <Ledger />}
      {tab === "compliance" && <ComplianceMatrix />}
      {tab === "lab" && <Lab />}
      {tab === "incident" && <Incident />}
      {tab === "export" && <AuditExport />}
    </div>
  );
}

function Policies() {
  const q = useApi<Catalog>(["policy-catalog"], "/api/policy/catalog");
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const c = q.data!;
  return (
    <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
      <Card title={`Policy set ${c.version}`} subtitle="Executable logic: backend/app/core/policy.py · metadata: fixtures/policies/policies.yaml">
        <DataTable label="Policies" columns={[{ key: "id", label: "ID" }, { key: "title", label: "Title" }, { key: "severity", label: "Severity" }, { key: "description", label: "Rule" }, { key: "denials", label: "Denials" }, { key: "references", label: "References (informational)" }]} rows={c.policies} />
      </Card>
      <Card title="Role → action grants (RBAC)">
        <DataTable columns={[{ key: "role", label: "Role" }, { key: "actions", label: "Actions" }]} rows={Object.entries(c.role_actions).map(([role, actions]) => ({ role, actions: actions.join(", ") }))} />
        <div className="mt-3 text-xs"><b>Approver roles:</b> {Object.entries(c.approver_roles).map(([k, v]) => `${k}: ${v.join(", ")}`).join(" · ")}</div>
      </Card>
    </div>
  );
}

function Trace() {
  const [filter, setFilter] = useState("");
  const q = useApi<(Decision & { checks: Decision["checks"] })[]>(["decisions", filter], `/api/policy/decisions?limit=300${filter ? `&decision=${filter}` : ""}`);
  const qc = useQueryClient();
  const [form, setForm] = useState({ action: "export", label: "RESTRICTED", destination: "personal_email", as_user: "" });
  const ev = useMutation({ mutationFn: () => post<Decision & { evaluated_for: string }>("/api/policy/evaluate", { ...form, as_user: form.as_user || undefined }), onSuccess: () => qc.invalidateQueries({ queryKey: ["decisions"] }) });
  return (
    <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
      <Card title="Live decision trace" subtitle="Every policy evaluation, newest first. Expand for the ordered checks." actions={
        <select className="input !py-1 text-xs" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Decision filter"><option value="">All</option><option>ALLOW</option><option>DENY</option></select>}>
        {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : <DecisionList decisions={q.data!} />}
      </Card>
      <Card title="Evaluate a hypothetical request" subtitle="Nothing is executed; the decision is recorded.">
        <div className="space-y-2 text-xs">
          {(["action", "label", "destination", "as_user"] as const).map((k) => (
            <label key={k} className="flex flex-col gap-1">{k}{k === "label" ? (
              <select className="input" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}>{["PUBLIC", "INTERNAL", "RESTRICTED", "UNKNOWN"].map((l) => <option key={l}>{l}</option>)}</select>
            ) : <input className="input" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} placeholder={k === "as_user" ? "(security officer / auditor only)" : ""} />}</label>
          ))}
          <button className="btn btn-primary" onClick={() => ev.mutate()} disabled={ev.isPending}><Play className="h-4 w-4" /> Evaluate</button>
          {ev.error ? <ErrorBox error={ev.error} /> : null}
          {ev.data && <DecisionList decisions={[ev.data.data]} />}
        </div>
      </Card>
    </div>
  );
}

function Classification() {
  const q = useApi<{ documents: Record<string, unknown>[]; work_orders: Record<string, unknown>[]; access_matrix: Record<string, unknown>[]; labels: Record<string, string> }>(["classification"], "/api/governance/classification");
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const d = q.data!;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">{Object.entries(d.labels).map(([k, v]) => <Card key={k} title={k}><div className="muted text-xs">{v}</div></Card>)}</div>
      <Card title="Who can read which label (computed from POL-003)">
        <DataTable columns={[{ key: "user", label: "User" }, { key: "persona", label: "Persona" }, { key: "PUBLIC", label: "PUBLIC" }, { key: "INTERNAL", label: "INTERNAL" }, { key: "RESTRICTED", label: "RESTRICTED" }, { key: "UNKNOWN", label: "UNKNOWN" }].map((c) => ["PUBLIC", "INTERNAL", "RESTRICTED", "UNKNOWN"].includes(c.key) ? { ...c, render: (r: Record<string, unknown>) => <Badge tone={r[c.key] ? "teal" : "red"}>{r[c.key] ? "allow" : "deny"}</Badge> } : c)} rows={d.access_matrix} />
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Documents by label"><DataTable columns={[{ key: "classification", label: "Label" }, { key: "n", label: "Count" }]} rows={d.documents} /></Card>
        <Card title="Work orders by label"><DataTable columns={[{ key: "classification", label: "Label" }, { key: "n", label: "Count" }]} rows={d.work_orders} /></Card>
      </div>
    </div>
  );
}

function ToolPerms() {
  const q = useApi<{ tools: Record<string, unknown>[]; rejected: Record<string, unknown>[]; allowlist: Record<string, unknown>[] }>(["bridge-tools"], "/api/bridge/tools");
  const g = useApi<{ tool_invocations: Record<string, unknown>[]; export_tool_executions: number }>(["gov-state"], "/api/governance/state");
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  return (
    <div className="space-y-4">
      <Card title="Registered tools" subtitle="Agents get the intersection of their own grants and the requesting human's; each call is evaluated per invocation.">
        <DataTable columns={[{ key: "name", label: "Tool" }, { key: "version", label: "Version" }, { key: "action", label: "Action" }, { key: "label", label: "Data label" }, { key: "destination", label: "Destination" }, { key: "pin_ok", label: "Pin OK" }, { key: "invocations", label: "Executions" }]} rows={q.data!.tools} />
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Rejected registrations"><DataTable columns={[{ key: "name", label: "Tool" }, { key: "version", label: "Version" }, { key: "reason", label: "Reason" }, { key: "ts", label: "When" }]} rows={q.data!.rejected} /></Card>
        <Card title="Invocation outcomes">{g.data && <><Kpi label="records.export_email executions" value={g.data.export_tool_executions} tone="teal" /><div className="mt-2"><DataTable columns={[{ key: "tool", label: "Tool" }, { key: "status", label: "Status" }, { key: "n", label: "Count" }]} rows={g.data.tool_invocations} /></div></>}</Card>
      </div>
    </div>
  );
}

function Ledger() {
  const q = useApi<{ total: number; items: AuditEv[] }>(["audit"], "/api/audit/events?limit=300");
  const v = useMutation({ mutationFn: () => post<{ valid: boolean; checked: number; head?: string; broken_at?: string; reason?: string; limits?: string }>("/api/audit/verify", {}) });
  return (
    <Card title="Evidence ledger (hash-chained audit log)" subtitle="Tamper-evident, not tamper-proof: a privileged host administrator can rewrite the file and recompute the chain." actions={
      <button className="btn btn-primary !py-1" onClick={() => v.mutate()} data-testid="verify-chain">Verify chain</button>}>
      {v.error ? <ErrorBox error={v.error} /> : null}
      {v.data && <div role="status" className={`mb-3 rounded-lg border p-2 text-xs ${v.data.data.valid ? "border-teal/40 bg-teal/10" : "border-blocked/40 bg-blocked/10"}`} data-testid="verify-result">
        {v.data.data.valid ? `Chain valid: ${v.data.data.checked} events, head ${v.data.data.head?.slice(0, 16)}...` : `Chain broken at ${v.data.data.broken_at}: ${v.data.data.reason}`}</div>}
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : (
        <DataTable label="Audit events" columns={[{ key: "seq", label: "#" }, { key: "ts", label: "Time", render: (r) => datetime(String(r.ts)) }, { key: "actor", label: "Actor" }, { key: "kind", label: "Kind" }, { key: "summary", label: "Summary" }, { key: "hash", label: "Hash", render: (r) => <code className="text-[10px]">{String(r.hash).slice(0, 12)}...</code> }]} rows={q.data!.items} maxHeight={480} />
      )}
    </Card>
  );
}

export function ComplianceMatrix() {
  const q = useApi<Record<string, unknown>[]>(["compliance"], "/api/compliance/matrix");
  return (
    <Card title="Compliance mapping (informational)" subtitle="Requires qualified compliance review. No certification, accreditation or CMMC level is claimed.">
      {q.isLoading ? <Loading /> : q.error ? <ErrorBox error={q.error} /> : <DataTable label="Compliance matrix" columns={[{ key: "control", label: "Control" }, { key: "implementation", label: "Implementation" }, { key: "status", label: "Status" }, { key: "references", label: "References" }]} rows={q.data!} />}
    </Card>
  );
}

function Lab() {
  const m = useMutation({ mutationFn: () => post<LabRow[]>("/api/policy/tests/run") });
  const rows = m.data?.data ?? [];
  return (
    <Card title="Security Test Lab" subtitle="Each scenario performs the real operation against the live controls and compares observed vs expected." actions={
      <button className="btn btn-primary" onClick={() => m.mutate()} disabled={m.isPending} data-testid="run-lab"><Play className="h-4 w-4" /> {m.isPending ? "Running..." : "Run all 12 scenarios"}</button>}>
      {m.error ? <ErrorBox error={m.error} /> : null}
      {rows.length > 0 && (
        <div className="space-y-2" data-testid="lab-results">
          <div className="flex gap-2"><Badge tone={rows.every((r) => r.passed) ? "teal" : "red"}>{rows.filter((r) => r.passed).length}/{rows.length} passed</Badge></div>
          <DataTable label="Security scenarios" columns={[{ key: "title", label: "Scenario" }, { key: "expected", label: "Expected" }, { key: "observed", label: "Observed", render: (r) => <Badge tone={r.observed === "ALLOW" ? "teal" : "red"}>{String(r.observed)}</Badge> }, { key: "passed", label: "Passed" }, { key: "policy_id", label: "Policy" }, { key: "tool_invocations", label: "Tool execs" }, { key: "reason", label: "Reason" }, { key: "ts", label: "Time", render: (r) => datetime(String(r.ts)) }]} rows={rows} maxHeight={520} />
        </div>
      )}
    </Card>
  );
}

function Incident() {
  const qc = useQueryClient();
  const g = useApi<{ kill_switch: boolean; pending_approvals: number; decisions: { n: number; denied: number } }>(["gov-state"], "/api/governance/state");
  const k = useMutation({ mutationFn: (on: boolean) => post("/api/governance/kill-switch", { on }), onSuccess: () => qc.invalidateQueries({ queryKey: ["gov-state"] }) });
  const on = g.data?.kill_switch;
  return (
    <Card title="Governance kill switch (POL-009)" subtitle="Stops new tool calls and workflows and cancels active runs. Security officer only (server-enforced).">
      {g.data && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Kpi label="Kill switch" value={on ? "ON" : "off"} tone={on ? "red" : "teal"} />
            <Kpi label="Decisions" value={g.data.decisions.n} />
            <Kpi label="Denied" value={g.data.decisions.denied ?? 0} tone="red" />
            <Kpi label="Pending approvals" value={g.data.pending_approvals} tone="amber" />
          </div>
          <button className={`btn ${on ? "btn-primary" : "btn-danger"}`} onClick={() => k.mutate(!on)} disabled={k.isPending} data-testid="kill-switch"><Power className="h-4 w-4" /> {on ? "Release kill switch" : "Activate kill switch"}</button>
          {k.error ? <ErrorBox error={k.error} /> : null}
        </div>
      )}
    </Card>
  );
}

function AuditExport() {
  const [err, setErr] = useState<unknown>(null);
  return (
    <Card title="Audit export" subtitle="JSON export of the full chain with embedded verification result. Auditor and security officer only.">
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={() => download("/api/audit/export", "flying_florina_audit_chain.json").catch(setErr)} data-testid="audit-export"><Download className="h-4 w-4" /> Download audit chain (JSON)</button>
        <button className="btn btn-ghost" onClick={async () => { try { setErr(null); const r = await post<{ download: string }>("/api/reports/generate", { kind: "audit_packet", fmt: "json" }); await download(r.data.download, "audit_packet.json"); } catch (e) { setErr(e); } }}>Generate audit packet report</button>
      </div>
      {err ? <div className="mt-2"><ErrorBox error={err} /></div> : null}
      <p className="muted mt-3 text-xs">Verify an exported file offline by POSTing its <code>events</code> array to <code>/api/audit/verify</code>; editing or deleting any event breaks verification from that point on.</p>
    </Card>
  );
}
