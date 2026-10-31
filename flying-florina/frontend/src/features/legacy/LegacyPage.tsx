import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ScanSearch, ShieldCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { DataTable } from "@/components/DataTable";
import { DependencyGraph } from "@/components/DependencyGraph";
import { Badge, Card, ErrorBox, Kpi, Loading, PageHeader, Tabs } from "@/components/ui";
import { BridgeTestRunner, Roadmap, Workspace } from "@/components/Workspace";
import { Chart } from "@/components/Chart";
import { download, post, upload } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import type { GraphEdge, GraphNode, Recommendation, RoadmapPhase } from "@/lib/types";

type Landscape = {
  nodes: GraphNode[]; edges: GraphEdge[]; findings: Record<string, unknown>[]; unknowns: Record<string, unknown>[];
  hotspots: Record<string, unknown>[]; bounded_contexts: { name: string; objects: string[] }[]; stale_docs: Record<string, unknown>[];
  batch_windows: Record<string, unknown>[]; sources: { source: string; kind: string; summary: Record<string, number> }[];
  summary: { systems: number; tables: number; apis: number; findings: number; high: number; medium: number; unknowns: number };
};
type Recommend = {
  recommendations: Recommendation[]; roadmap: RoadmapPhase[]; current_state: { systems: GraphNode[]; edges: GraphEdge[] };
  target_state: { layers: string[]; new_components: string[] }; diff: { change: string; component: string }[]; executive_brief: string;
  matrix: Record<string, unknown>[];
};
type Bundle = { bundle_id: string; static_checks: { check: string; passed: boolean }[]; mapping: Record<string, unknown>[]; preview: Record<string, string>; files: Record<string, unknown>[] };

export function LegacyPage() {
  const qc = useQueryClient();
  const ls = useApi<Landscape>(["landscape"], "/api/legacy/graph");
  const rec = useMutation({ mutationFn: () => post<Recommend>("/api/legacy/recommend") });
  const gen = useMutation({ mutationFn: () => post<Bundle>("/api/bridge/generate", { capability: "part_availability", source_id: "mro_view" }) });
  const [tab, setTab] = useState("current");
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<unknown>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onUpload = async (f?: File) => {
    if (!f) return;
    setUploadErr(null);
    try {
      const r = await upload<{ kind: string; filename: string; summary: Record<string, number>; findings: unknown[] }>("/api/legacy/import", f);
      setUploadMsg(`Imported ${r.data.filename} as ${r.data.kind}: ${JSON.stringify(r.data.summary)} · ${r.data.findings.length} finding(s). Parsed only, never executed.`);
      qc.invalidateQueries({ queryKey: ["landscape"] });
    } catch (e) {
      setUploadErr(e);
    } finally {
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const r = rec.data?.data;
  return (
    <div className="space-y-4">
      <PageHeader
        title="Legacy X-Ray"
        subtitle="Offline metadata analysis of schemas, APIs, batch files and source bundles. Nothing uploaded is executed. Unknowns are shown, not assumed."
        icon={<ScanSearch className="h-5 w-5" />}
        actions={
          <>
            <input ref={fileRef} type="file" className="hidden" accept=".sql,.json,.yaml,.yml,.csv,.xml,.zip" onChange={(e) => onUpload(e.target.files?.[0])} data-testid="legacy-upload" />
            <button className="btn btn-ghost" onClick={() => fileRef.current?.click()}><Upload className="h-4 w-4" /> Import metadata</button>
            <button className="btn btn-ghost" onClick={() => rec.mutate()} disabled={rec.isPending} data-testid="recommend">Recommend modernization path</button>
            <button className="btn btn-ghost" data-testid="export-blueprint" onClick={async () => {
              try { const r = await post<{ download: string }>("/api/reports/generate", { kind: "modernization_blueprint", fmt: "pdf" }); await download(r.data.download, "modernization_blueprint.pdf"); }
              catch (e) { setUploadErr(e); }
            }}>Export Modernization Blueprint</button>
            <button className="btn btn-primary" onClick={() => { gen.mutate(); setTab("adapter"); }} disabled={gen.isPending} data-testid="generate-bridge">
              <ShieldCheck className="h-4 w-4" /> Generate safe read-only bridge
            </button>
          </>
        }
      />
      {uploadMsg && <div role="status" className="rounded-lg border border-teal/40 bg-teal/10 p-2 text-xs">{uploadMsg}</div>}
      {uploadErr ? <ErrorBox error={uploadErr} /> : null}
      {ls.isLoading ? <Loading label="Parsing bundled fixtures and uploads" /> : ls.error ? <ErrorBox error={ls.error} /> : ls.data && (
        <>
          <div className="grid grid-cols-2 gap-2 md:grid-cols-6" data-testid="legacy-kpis">
            <Kpi label="Sources parsed" value={ls.data.sources.length} />
            <Kpi label="Systems" value={ls.data.summary.systems} />
            <Kpi label="Tables" value={ls.data.summary.tables} />
            <Kpi label="APIs" value={ls.data.summary.apis} />
            <Kpi label="High findings" value={ls.data.summary.high} tone="red" />
            <Kpi label="Unknowns" value={ls.data.summary.unknowns} tone="amber" />
          </div>
          <Card title="Dependency map" subtitle="Bundled fictional 20-year-old MRO landscape plus your uploads. Click a node for evidence.">
            <DependencyGraph nodes={ls.data.nodes.filter((n) => ["system", "api", "unknown", "file", "event"].includes(n.type))} edges={ls.data.edges} />
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Coupling hotspots"><DataTable columns={[{ key: "system", label: "System" }, { key: "name", label: "Name" }, { key: "integration_degree", label: "Integrations" }]} rows={ls.data.hotspots} /></Card>
            <Card title="Candidate bounded contexts">
              <ul className="space-y-1 text-xs">{ls.data.bounded_contexts.map((b) => <li key={b.name}><b>{b.name}:</b> {b.objects.join(", ")}</li>)}</ul>
              <div className="mt-3 text-xs"><b>Batch windows:</b> {ls.data.batch_windows.map((b) => `${b.name} (${b.window})`).join("; ")}</div>
              <div className="mt-1 text-xs"><b>Stale documentation:</b> {ls.data.stale_docs.map((s) => `${s.name} (${s.last_doc_update})`).join("; ")}</div>
            </Card>
          </div>
          <AnalyticsCharts ls={ls.data} recs={r?.recommendations} onNeedRecs={() => !r && !rec.isPending && rec.mutate()} />
          <Card title="Findings"><DataTable label="Findings" columns={[{ key: "severity", label: "Severity" }, { key: "kind", label: "Kind" }, { key: "object", label: "Object" }, { key: "detail", label: "Detail" }, { key: "source", label: "Source" }]} rows={ls.data.findings} /></Card>
          <Card title="Unknowns to resolve with system owners"><DataTable columns={[{ key: "id", label: "ID" }, { key: "question", label: "Question" }, { key: "why", label: "Why it matters" }]} rows={ls.data.unknowns} /></Card>
          <Card title="Parsed sources"><DataTable columns={[{ key: "source", label: "Source" }, { key: "kind", label: "Kind" }, { key: "summary", label: "Summary" }]} rows={ls.data.sources} /></Card>
        </>
      )}

      <Card title="Modernization workspace">
        <Tabs label="Modernization views" active={tab} onChange={(t) => { setTab(t); if (!r && t !== "adapter" && t !== "validation") rec.mutate(); }} tabs={[
          { id: "current", label: "Current State" }, { id: "target", label: "Target State" }, { id: "diff", label: "Diff" }, { id: "roadmap", label: "Phased Roadmap" },
          { id: "adapter", label: "Adapter Preview" }, { id: "validation", label: "Validation" }, { id: "brief", label: "Executive Brief" }]} />
        <div className="mt-3">
          {rec.isPending && <Loading />}
          {rec.error ? <ErrorBox error={rec.error} /> : null}
          {!r && !rec.isPending && !["adapter", "validation"].includes(tab) && <button className="btn btn-primary" onClick={() => rec.mutate()}>Analyze and recommend</button>}
          {r && tab === "current" && (
            <div className="space-y-3">
              <DataTable columns={[{ key: "id", label: "System" }, { key: "label", label: "Name" }, { key: "kind", label: "Kind" }, { key: "criticality", label: "Criticality" }]} rows={r.current_state.systems as unknown as Record<string, unknown>[]} />
              <Workspace blocks={[{ type: "recommendations", items: r.recommendations }]} />
            </div>
          )}
          {r && tab === "target" && (
            <div className="space-y-2" data-testid="target-state">
              {r.target_state.layers.map((l, i) => (
                <div key={l} className="rounded-lg border border-token p-2 text-sm" style={{ marginLeft: i * 16 }}>{i + 1}. {l}</div>
              ))}
              <div className="text-xs"><b>New components:</b> {r.target_state.new_components.join(", ")}</div>
              <DataTable columns={[{ key: "approach", label: "Approach" }, { key: "use_cases", label: "Use cases" }, { key: "strengths", label: "Strengths" }, { key: "limitations", label: "Limitations" }, { key: "risks", label: "Risks" }, { key: "recommendation", label: "Recommendation" }]} rows={r.matrix} />
            </div>
          )}
          {r && tab === "diff" && (
            <ul className="space-y-1 text-sm">{r.diff.map((d) => <li key={d.component} className="flex gap-2"><Badge tone={d.change === "add" ? "teal" : d.change === "restrict" ? "red" : d.change === "keep" ? "gray" : "amber"}>{d.change}</Badge>{d.component}</li>)}</ul>
          )}
          {r && tab === "roadmap" && <Roadmap items={r.roadmap} />}
          {tab === "adapter" && (
            gen.isPending ? <Loading label="Generating adapter bundle" /> : gen.error ? <ErrorBox error={gen.error} /> : gen.data ? (
              <div className="space-y-3" data-testid="adapter-preview">
                <div className="text-sm">Bundle <b>{gen.data.data.bundle_id}</b> · {gen.data.data.files.length} files · not executed yet.</div>
                <DataTable columns={[{ key: "legacy", label: "Legacy" }, { key: "canonical", label: "Canonical" }, { key: "type", label: "Type" }, { key: "note", label: "Note" }]} rows={gen.data.data.mapping} />
                <pre className="max-h-72 overflow-auto rounded-lg bg-navy p-3 text-[11px] text-offwhite">{gen.data.data.preview["adapter/app.py"]}</pre>
                <BridgeTestRunner bundleId={gen.data.data.bundle_id} />
              </div>
            ) : <button className="btn btn-primary" onClick={() => gen.mutate()}>Generate safe read-only bridge</button>
          )}
          {tab === "validation" && (gen.data ? (
            <DataTable columns={[{ key: "check", label: "Static check (no execution)" }, { key: "passed", label: "Passed" }]} rows={gen.data.data.static_checks} />
          ) : <div className="muted text-xs">Generate a bridge first; static checks run without executing code, runtime tests run on request.</div>)}
          {r && tab === "brief" && <div className="text-sm leading-relaxed">{r.executive_brief}</div>}
        </div>
      </Card>
    </div>
  );
}

const RISK: Record<string, number> = { low: 1, medium: 2, high: 3 };

function effortWeeks(e: string): number {
  const m = /([\d.]+)\s*-\s*([\d.]+)/.exec(e);
  return m ? (Number(m[1]) + Number(m[2])) / 2 : Number((/([\d.]+)/.exec(e) ?? [0, 0])[1]);
}

function AnalyticsCharts({ ls, recs, onNeedRecs }: { ls: Landscape; recs?: Recommendation[]; onNeedRecs: () => void }) {
  const kinds: Record<string, number> = {};
  ls.findings.forEach((f) => { const k = String(f.kind); kinds[k] = (kinds[k] ?? 0) + 1; });
  const apis = ls.nodes.filter((n) => n.type === "api" || n.type === "system");
  const readiness = apis.map((n) => {
    const fs = ls.findings.filter((f) => String(f.source ?? "").toLowerCase().includes(String(n.label).split(" ")[0].toLowerCase()));
    const high = fs.filter((f) => f.severity === "high").length;
    return { system: n.label, type: n.type, auth: Array.isArray((n as unknown as { auth?: unknown }).auth) ? ((n as unknown as { auth: string[] }).auth).join(", ") : String((n as unknown as { auth?: string }).auth ?? "-"),
      findings: fs.length, high, readiness: n.type === "api" ? (high ? "blocked: fix high findings" : fs.length ? "needs facade" : "ready (read-only)") : "wrap via adapter" };
  });
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title="Technical debt distribution" subtitle="Findings by kind (parsed metadata)">
        <Chart title="Technical debt" spec={{ kind: "bar", x: Object.keys(kinds).map((k) => k.replace(/_/g, " ")), series: [{ name: "Findings", data: Object.values(kinds) }] }} height={260} />
      </Card>
      <Card title="Migration risk vs effort" subtitle="Per recommendation; effort is an assumption range midpoint" actions={!recs ? <button className="btn btn-ghost !py-1 text-xs" onClick={onNeedRecs}>Compute</button> : undefined}>
        {recs ? (
          <Chart title="Risk vs effort" spec={{ kind: "scatter", x: [], xLabel: "Effort (engineer-weeks, assumption)", yLabel: "Migration risk (1 low – 3 high)",
            series: [{ name: "Recommendations", data: [], points: recs.map((r) => [effortWeeks(r.effort_assumption), RISK[r.migration_risk] ?? 2, `${r.id} ${r.title}`]) }] }} height={260} />
        ) : <p className="muted p-6 text-center text-xs">Run “Recommend modernization path” to plot recommendations.</p>}
      </Card>
      <Card title="API readiness matrix" subtitle="Derived from declared auth and findings per system/API">
        <DataTable label="API readiness" maxHeight={260} columns={[{ key: "system", label: "System / API" }, { key: "auth", label: "Auth (metadata)" }, { key: "findings", label: "Findings" }, { key: "readiness", label: "Readiness" }]} rows={readiness} />
      </Card>
    </div>
  );
}
