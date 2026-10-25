import { Gauge, Play } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { Workspace } from "@/components/Workspace";
import { useApi, useWorkflow } from "@/lib/hooks";

export function QualityPage() {
  const incidents = useApi<Record<string, unknown>[]>(["incidents"], "/api/incidents");
  const wf = useWorkflow();
  return (
    <div className="space-y-4">
      <PageHeader title="Engineering Quality" subtitle="Nonconformance investigation, corrective-action drafts and supplier documentation checks. Dispositions require a quality approver." icon={<Gauge className="h-5 w-5" />}
        actions={<button className="btn btn-primary" disabled={wf.pending} onClick={() => wf.run_({ query: "Draft a corrective action for the worst supplier nonconformance and check supplier documentation quality." })}><Play className="h-4 w-4" /> Investigate nonconformance</button>} />
      <Card title="Seeded incidents (synthetic)">
        {incidents.isLoading ? <Loading /> : incidents.error ? <ErrorBox error={incidents.error} /> : <DataTable label="Incidents" columns={[{ key: "id", label: "ID" }, { key: "title", label: "Title" }, { key: "kind", label: "Kind" }, { key: "severity", label: "Severity" }, { key: "status", label: "Status" }, { key: "opened", label: "Opened" }, { key: "related", label: "Related" }]} rows={incidents.data!} />}
      </Card>
      {wf.pending && <Loading label="Compliance agent working" />}
      {wf.error ? <ErrorBox error={wf.error} /> : null}
      {wf.run && <Workspace blocks={wf.run.state.workspace} runId={wf.run.run_id} />}
    </div>
  );
}
