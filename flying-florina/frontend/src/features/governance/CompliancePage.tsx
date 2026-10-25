import { FileCheck2, Play } from "lucide-react";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { Badge, Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { download, post } from "@/lib/api";
import { useApi, useWorkflow } from "@/lib/hooks";
import { Workspace } from "@/components/Workspace";
import { ComplianceMatrix } from "./TrustPage";

type Docs = { items: (Record<string, unknown> & { issues: string[] })[]; withheld: number };

export function CompliancePage() {
  const docs = useApi<Docs>(["docs"], "/api/documents");
  const wf = useWorkflow();
  const [err, setErr] = useState<unknown>(null);
  const packet = async () => {
    try {
      setErr(null);
      if (!wf.run) return;
      const r = await post<{ download: string }>("/api/reports/generate", { kind: "evidence_manifest", fmt: "json", run_id: wf.run.run_id });
      await download(r.data.download, "evidence_manifest.json");
    } catch (e) { setErr(e); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Compliance Evidence" subtitle="Revision-aware references, missing provenance, approvals and exportable evidence packets. A checklist, never a certification or automatic sign-off." icon={<FileCheck2 className="h-5 w-5" />}
        actions={<>
          <button className="btn btn-primary" onClick={() => wf.run_({ query: "Show which maintenance documents are stale or missing provenance." })} disabled={wf.pending}><Play className="h-4 w-4" /> Check document freshness</button>
          <button className="btn btn-ghost" onClick={packet} disabled={!wf.run}>Export evidence manifest</button>
        </>} />
      {err ? <ErrorBox error={err} /> : null}
      {wf.error ? <ErrorBox error={wf.error} /> : null}
      {wf.run && <Workspace blocks={wf.run.state.workspace} runId={wf.run.run_id} />}
      <Card title="Document control status" subtitle={docs.data ? `${docs.data.withheld} withheld by classification` : ""}>
        {docs.isLoading ? <Loading /> : docs.error ? <ErrorBox error={docs.error} /> : (
          <DataTable label="Documents" columns={[{ key: "id", label: "ID" }, { key: "title", label: "Title" }, { key: "revision", label: "Rev" }, { key: "review_due", label: "Review due" }, { key: "has_provenance", label: "Provenance", render: (r) => <Badge tone={r.has_provenance ? "teal" : "red"}>{r.has_provenance ? "hash on file" : "missing"}</Badge> }, { key: "status", label: "Status" }, { key: "issues", label: "Issues", render: (r) => (r.issues as string[]).join("; ") || "-" }]} rows={docs.data!.items} />
        )}
      </Card>
      <ComplianceMatrix />
    </div>
  );
}
