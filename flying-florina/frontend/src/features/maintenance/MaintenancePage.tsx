import { Wrench } from "lucide-react";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHeader, Tabs } from "@/components/ui";
import { Markdown } from "@/components/Workspace";
import { get } from "@/lib/api";
import { useApi } from "@/lib/hooks";

type WOs = { total: number; items: Record<string, unknown>[]; withheld_by_classification: number; duplicates: Record<string, unknown>[] };
type Docs = { items: (Record<string, unknown> & { id: string; issues: string[] })[]; withheld: number };

export function MaintenancePage() {
  const [status, setStatus] = useState("open");
  const [tab, setTab] = useState("wo");
  const wo = useApi<WOs>(["wo", status], `/api/maintenance/work-orders?status=${status}&limit=500`);
  const docs = useApi<Docs>(["docs"], "/api/documents");
  const [doc, setDoc] = useState<{ title: string; body: string; revision: string } | null>(null);
  const [docErr, setDocErr] = useState<unknown>(null);
  const open = async (id: string) => {
    setDocErr(null);
    try {
      setDoc((await get<{ title: string; body: string; revision: string }>(`/api/documents/${id}`)).data);
    } catch (e) {
      setDoc(null);
      setDocErr(e);
    }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Maintenance & MRO" subtitle="Work orders and revision-aware technical references. No automatic sign-off." icon={<Wrench className="h-5 w-5" />} />
      <Tabs label="Maintenance views" active={tab} onChange={setTab} tabs={[{ id: "wo", label: "Work orders" }, { id: "docs", label: "Technical references" }, { id: "dup", label: "Duplicates" }]} />
      {tab === "wo" && (
        <Card title="Work orders" subtitle={wo.data ? `${wo.data.total} shown · ${wo.data.withheld_by_classification} withheld by classification for your persona` : ""} actions={
          <select className="input !py-1 text-xs" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter">
            {["open", "closed", "awaiting_parts", "in_progress", "planned"].map((s) => <option key={s}>{s}</option>)}
          </select>}>
          {wo.isLoading ? <Loading /> : wo.error ? <ErrorBox error={wo.error} /> : (
            <DataTable label="Work orders" columns={[{ key: "id", label: "WO" }, { key: "aircraft_id", label: "Aircraft" }, { key: "status", label: "Status" }, { key: "priority", label: "Priority" }, { key: "opened", label: "Opened" }, { key: "part_number", label: "Part" }, { key: "assigned_tech", label: "Tech" }, { key: "source_system", label: "Source" }, { key: "classification", label: "Label" }, { key: "description", label: "Description" }]} rows={wo.data!.items} />
          )}
        </Card>
      )}
      {tab === "docs" && (
        <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
          <Card title="Document library" subtitle={docs.data ? `${docs.data.withheld} document(s) withheld by classification` : ""}>
            {docs.isLoading ? <Loading /> : docs.error ? <ErrorBox error={docs.error} /> : (
              <DataTable label="Documents" columns={[
                { key: "id", label: "ID", render: (r) => <button className="font-semibold text-purple underline dark:text-lavender" onClick={() => open(String(r.id))}>{String(r.id)}</button> },
                { key: "title", label: "Title" }, { key: "revision", label: "Rev" }, { key: "effective_date", label: "Effective" }, { key: "status", label: "Status" }, { key: "classification", label: "Label" },
                { key: "issues", label: "Issues", render: (r) => (r.issues as string[]).length ? (r.issues as string[]).map((i) => <Badge key={i} tone="amber">{i}</Badge>) : <Badge tone="teal">ok</Badge> }]} rows={docs.data!.items} />
            )}
          </Card>
          <Card title="Reader" subtitle="Instruction-like text inside documents is quarantined and treated as data.">
            {docErr ? <ErrorBox error={docErr} /> : doc ? <div><div className="mb-2 font-semibold">{doc.title} · rev {doc.revision}</div><Markdown text={doc.body} /></div> : <div className="muted text-xs">Select a document. Access is checked per document by the policy engine.</div>}
          </Card>
        </div>
      )}
      {tab === "dup" && wo.data && (
        <Card title="Duplicate work orders across systems (seeded incident INC-007)">
          <div className="mb-2 grid grid-cols-2 gap-2 md:grid-cols-4"><Kpi label="Duplicates" value={wo.data.duplicates.length} tone="amber" /></div>
          <DataTable columns={[{ key: "id", label: "WO" }, { key: "duplicate_of", label: "Duplicate of" }, { key: "aircraft_id", label: "Aircraft" }, { key: "source_system", label: "Source" }, { key: "description", label: "Description" }]} rows={wo.data.duplicates} />
        </Card>
      )}
    </div>
  );
}
