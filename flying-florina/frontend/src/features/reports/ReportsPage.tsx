import { useQueryClient } from "@tanstack/react-query";
import { Download, FileBarChart } from "lucide-react";
import { useState } from "react";
import { DataTable } from "@/components/DataTable";
import { Card, ErrorBox, PageHeader } from "@/components/ui";
import { download, post } from "@/lib/api";
import { datetime } from "@/lib/format";
import { useApi } from "@/lib/hooks";

const KINDS: Record<string, string[]> = {
  executive_brief: ["pdf", "md", "html"], one_page_brief: ["pdf", "md"], architecture: ["md"], work_orders: ["csv"], audit_packet: ["json"], demo_script: ["md"],
};

export function ReportsPage() {
  const qc = useQueryClient();
  const list = useApi<Record<string, unknown>[]>(["reports"], "/api/reports");
  const [kind, setKind] = useState("executive_brief");
  const [fmt, setFmt] = useState("pdf");
  const [err, setErr] = useState<unknown>(null);
  const [last, setLast] = useState<string | null>(null);
  const gen = async () => {
    try {
      setErr(null);
      const r = await post<{ id: string; download: string; sha256: string }>("/api/reports/generate", { kind, fmt });
      setLast(`${r.data.id} · SHA-256 ${r.data.sha256.slice(0, 16)}...`);
      await download(r.data.download, `${kind}.${fmt}`);
      qc.invalidateQueries({ queryKey: ["reports"] });
    } catch (e) { setErr(e); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Reports & Exports" subtitle="Generated locally (ReportLab PDF, HTML, Markdown, CSV, JSON). Exports are policy-checked; external destinations are never offered." icon={<FileBarChart className="h-5 w-5" />} />
      <Card title="Generate">
        <div className="flex flex-wrap items-end gap-2 text-xs">
          <label className="flex flex-col gap-1">Report<select className="input" value={kind} onChange={(e) => { setKind(e.target.value); setFmt(KINDS[e.target.value][0]); }} aria-label="Report kind">{Object.keys(KINDS).map((k) => <option key={k}>{k}</option>)}</select></label>
          <label className="flex flex-col gap-1">Format<select className="input" value={fmt} onChange={(e) => setFmt(e.target.value)} aria-label="Format">{KINDS[kind].map((f) => <option key={f}>{f}</option>)}</select></label>
          <button className="btn btn-primary" onClick={gen} data-testid="generate-report"><Download className="h-4 w-4" /> Generate & download</button>
        </div>
        {last && <div role="status" className="mt-2 text-xs">Generated {last}</div>}
        {err ? <div className="mt-2"><ErrorBox error={err} /></div> : null}
        <p className="muted mt-2 text-xs">Workspace exports (PDF/MD/HTML/JSON) and evidence manifests are available from each answer in Mission Control.</p>
      </Card>
      <Card title="Your reports">
        {list.error ? <ErrorBox error={list.error} /> : <DataTable label="Reports" columns={[{ key: "ts", label: "Created", render: (r) => datetime(String(r.ts)) }, { key: "title", label: "Title" }, { key: "fmt", label: "Format" }, { key: "classification", label: "Label" }, { key: "sha256", label: "SHA-256", render: (r) => <code className="text-[10px]">{String(r.sha256).slice(0, 16)}</code> },
          { key: "id", label: "Download", render: (r) => <button className="text-purple underline dark:text-lavender" onClick={() => download(`/api/reports/${r.id}/download`, `${r.id}.${r.fmt}`).catch(setErr)}>{String(r.id)}</button> }]} rows={list.data ?? []} />}
      </Card>
    </div>
  );
}
