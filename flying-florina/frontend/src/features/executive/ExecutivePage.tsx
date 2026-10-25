import { Building2, Download, Play } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, Loading, PageHeader } from "@/components/ui";
import { Workspace } from "@/components/Workspace";
import { download, post } from "@/lib/api";
import { useWorkflow } from "@/lib/hooks";

export function ExecutivePage() {
  const wf = useWorkflow();
  const [err, setErr] = useState<unknown>(null);
  const gen = async (kind: string, fmt: string) => {
    try {
      setErr(null);
      const r = await post<{ download: string }>("/api/reports/generate", { kind, fmt });
      await download(r.data.download, `${kind}.${fmt}`);
    } catch (e) { setErr(e); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Executive Value Studio" subtitle="Validated findings turned into a pitch: roadmap, risks, API/MCP strategy and a transparent, assumption-driven ROI model. Never a promise of savings." icon={<Building2 className="h-5 w-5" />}
        actions={<button className="btn btn-primary" onClick={() => wf.run_({ query: "Create a 90-day modernization pitch for this customer." })} disabled={wf.pending} data-testid="run-pitch"><Play className="h-4 w-4" /> Create 90-day pitch</button>} />
      <Card title="Downloads">
        <div className="flex flex-wrap gap-2">
          <button className="btn btn-ghost" onClick={() => gen("executive_brief", "pdf")}><Download className="h-4 w-4" /> Client pitch (PDF)</button>
          <button className="btn btn-ghost" onClick={() => gen("one_page_brief", "pdf")}><Download className="h-4 w-4" /> One-page brief (PDF)</button>
          <button className="btn btn-ghost" onClick={() => gen("architecture", "md")}><Download className="h-4 w-4" /> Architecture (Markdown)</button>
          <button className="btn btn-ghost" onClick={() => gen("demo_script", "md")}><Download className="h-4 w-4" /> Demo video script</button>
        </div>
        {err ? <div className="mt-2"><ErrorBox error={err} /></div> : null}
      </Card>
      {wf.pending && <Loading label="Reporting agent assembling pitch" />}
      {wf.error ? <ErrorBox error={wf.error} /> : null}
      {wf.run && <Workspace blocks={wf.run.state.workspace} runId={wf.run.run_id} />}
    </div>
  );
}
