import { useState } from "react";
import { ApprovalCard } from "../components/ApprovalCard";
import { Badge, Card, Note, PageHeader, Segmented, Spinner, Table } from "../components/ui";
import { RoleSwitcher } from "../components/Layout";
import { useApi } from "../lib/api";
import { useApp } from "../lib/store";

export default function Approvals() {
  const { role, user } = useApp();
  const [filter, setFilter] = useState("open");
  const list = useApi<any[]>("/approvals", filter === "all" ? undefined : { status: filter }, 5000);
  const [sel, setSel] = useState<string | null>(null);
  const detail = useApi<any>(sel ? `/approvals/${sel}` : null);
  return (
    <div>
      <PageHeader title="Sherin's Manager Approval Center" subtitle="Material investment actions, production deployments, sensitive data changes and high-impact AI decisions need a human. Mandatory policy blocks cannot be approved.">
        <RoleSwitcher /><Badge tone="dark">{user}</Badge>
      </PageHeader>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Segmented label="Filter approvals" value={filter} onChange={setFilter} options={[{ value: "open", label: "Inbox" }, { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }, { value: "blocked", label: "Blocked" }, { value: "all", label: "All" }]} />
        <span className="text-xs text-muted">Acting as <strong>{role.replace(/_/g, " ")}</strong>. Requesters cannot decide their own requests; one person cannot sign twice.</span>
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <div className="space-y-3">
          {list.loading && !list.data ? <Spinner /> : (list.data ?? []).map((a) => (
            <div key={a.id} onClick={() => setSel(a.id)} className={`cursor-pointer rounded-2xl ${sel === a.id ? "ring-2 ring-flo-600" : ""}`}>
              <ApprovalCard a={a} onChange={() => { list.reload(); detail.reload(); }} />
            </div>))}
          {list.data?.length === 0 && <Card className="p-6 text-sm text-muted">Nothing here.</Card>}
        </div>
        <div>
          {!sel ? <Card className="p-6 text-sm text-muted">Select a request to inspect its risk evidence, Guardian checks, agent execution history and audit trail.</Card> : !detail.data ? <Spinner /> : (
            <Card className="space-y-4 p-5">
              <h2 className="font-display text-xl font-semibold text-flo-900">{detail.data.title}</h2>
              <p className="text-sm text-muted">{detail.data.summary}</p>
              {detail.data.guardian && <><h3 className="font-semibold">Guardian controls — <Badge tone={detail.data.guardian.decision === "BLOCK" ? "red" : detail.data.guardian.decision === "PASS" ? "green" : "amber"}>{detail.data.guardian.decision}</Badge></h3>
                <Table dense columns={[{ key: "name", label: "Control" }, { key: "status", label: "Result" }, { key: "detail", label: "Evidence" }]} rows={detail.data.guardian.checks} /></>}
              {detail.data.run && <><h3 className="font-semibold">Agent execution history ({detail.data.run.id})</h3>
                <ol className="space-y-0.5 text-xs">{detail.data.run.trace.map((t: any, i: number) => <li key={i}><code className="text-muted">{t.at.slice(11, 19)}</code> <Badge tone="slate">{t.node}</Badge> {t.message}</li>)}</ol></>}
              <h3 className="font-semibold">Audit trail</h3>
              <Table dense columns={[{ key: "ts", label: "Time" }, { key: "actor", label: "Actor" }, { key: "role", label: "Role" }, { key: "action", label: "Action" }]} rows={detail.data.audit} />
              <Note>Financial impact shown is exposure (notional), not profit or loss. Sherin does not claim losses prevented.</Note>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
