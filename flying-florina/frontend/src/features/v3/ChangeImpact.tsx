import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Download, GitBranch, Search } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { DependencyGraph } from "@/components/DependencyGraph";
import { Badge, Card, ErrorBox, Kpi, PageHeader, Skeleton } from "@/components/ui";
import { download, get, post } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { Banner } from "./common";

type Req = { id: string; title: string; status: string; modules: string[]; verification: { file: string; exists: boolean }[] };
type Analysis = { target: string; resolved: string[]; risk: string; error?: string; method: string; affected_modules: { module: string; distance: number; path: string; lines: number }[];
  affected_routes: string[]; affected_frontend: { file: string; calls: string[] }[]; recommended_tests: { test: string; via: string[]; distance: number }[];
  untested_affected_modules: string[]; requirements: Req[]; graph: { nodes: { id: string; label: string; distance: number }[]; edges: { source: string; target: string }[] } };
const EXAMPLES = ["app.global_intel.forecast", "app.core.policy", "/api/global/map", "ToolSpec", "app.llm.gateway"];

export function ChangeImpact() {
  const [params] = useSearchParams();
  const [target, setTarget] = useState(params.get("target") ?? "app.global_intel.forecast");
  const [q, setQ] = useState(target);
  const ov = useQuery({ queryKey: ["ci-ov"], queryFn: () => get<{ modules: number; tests: number; frontend_files: number; routes: number; top_fan_in: [string, number][]; traceability: Record<string, number> }>("/api/change-impact/overview") });
  const an = useQuery({ queryKey: ["ci", q], queryFn: () => get<Analysis>(`/api/change-impact/analyze?target=${encodeURIComponent(q)}`) });
  const tr = useQuery({ queryKey: ["ci-tr"], queryFn: () => get<{ project: string; requirements: Req[]; summary: Record<string, number> }>("/api/change-impact/traceability") });
  const [before, setBefore] = useState('{"OFFLINE_MODE": true, "LLM_ENABLED": "on", "FF_QWEN_MAX_TOKENS": 320}');
  const [after, setAfter] = useState('{"OFFLINE_MODE": false, "LLM_ENABLED": "on", "FF_QWEN_MAX_TOKENS": 512, "FF_NEW_FLAG": 1}');
  const cmp = useMutation({ mutationFn: () => post<{ changes: { key: string; kind: string; before: unknown; after: unknown; risk: string }[]; review_required: string[] }>("/api/change-impact/compare-config",
    { before: JSON.parse(before), after: JSON.parse(after) }) });
  const a = an.data?.data;
  const nodes: GraphNode[] = (a?.graph.nodes ?? []).map((n) => ({ id: n.id, label: n.label, type: n.distance === 0 ? "system" : n.distance === 1 ? "api" : "view" }));
  const edges: GraphEdge[] = (a?.graph.edges ?? []).map((e, i) => ({ id: `e${i}`, source: e.source, target: e.target, label: "imported by", kind: "depends" }));
  return (
    <div className="space-y-4">
      <PageHeader title="Software Change Impact Intelligence" icon={<GitBranch className="h-5 w-5" />}
        subtitle="Which modules, APIs, frontend screens, tests and requirements could a change affect? Static analysis of this repository plus a labelled synthetic requirement set." />
      <Banner>Static import analysis (Python ast + route decorators + test imports + TypeScript API references). Not line coverage and not a certification argument; results are evidence for an engineer to review.</Banner>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi label="Python modules" value={ov.data?.data.modules ?? "…"} /><Kpi label="API routes" value={ov.data?.data.routes ?? "…"} />
        <Kpi label="Test files" value={ov.data?.data.tests ?? "…"} /><Kpi label="Requirements missing verification" value={ov.data?.data.traceability.missing_verification ?? "…"} tone="amber" />
      </div>
      <Card title="Analyse a change" subtitle="Module (app.x.y), symbol (class/function), file, or API route">
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); setQ(target); }}>
          <input className="input w-80" value={target} onChange={(e) => setTarget(e.target.value)} aria-label="Change target" data-testid="ci-target" />
          <button className="btn btn-primary" type="submit"><Search className="h-4 w-4" />Analyse</button>
          {EXAMPLES.map((x) => <button type="button" key={x} className="rounded-full border border-token px-2.5 py-1 text-xs muted" onClick={() => { setTarget(x); setQ(x); }}>{x}</button>)}
          {a && !a.error && <button type="button" className="btn btn-ghost ml-auto text-xs" onClick={() => download(`/api/change-impact/report?target=${encodeURIComponent(q)}`, "release_impact.md")}><Download className="h-4 w-4" />Release impact report</button>}
        </form>
      </Card>
      {an.error ? <ErrorBox error={an.error} /> : !a ? <Skeleton className="h-80" /> : a.error ? <Banner tone="red">{a.error}</Banner> : (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm" data-testid="ci-summary">
            Resolved to <b>{a.resolved.join(", ")}</b> · risk <Badge tone={a.risk === "high" ? "red" : a.risk === "medium" ? "amber" : "teal"}>{a.risk}</Badge> ·
            {a.affected_modules.length} modules · {a.affected_routes.length} routes · {a.affected_frontend.length} frontend files · {a.recommended_tests.length} test files
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            <Card title="Dependency graph" subtitle="Target and everything that imports it (directly or transitively)"><DependencyGraph nodes={nodes} edges={edges} height={420} /></Card>
            <Card title="Regression tests to run first" subtitle="Ordered by import distance">
              <DataTable rows={a.recommended_tests.map((t) => ({ ...t, via: t.via.join(", ") }))} columns={[{ key: "test", label: "Test file" }, { key: "distance", label: "Hops" }, { key: "via", label: "Via" }]} />
              {!!a.untested_affected_modules.length && <p className="mt-2 text-xs text-warn">No test imports: {a.untested_affected_modules.join(", ")}</p>}
            </Card>
            <Card title="Affected modules"><DataTable rows={a.affected_modules as unknown as Record<string, unknown>[]} columns={[{ key: "module", label: "Module" }, { key: "distance", label: "Hops" }, { key: "lines", label: "Lines" }]} /></Card>
            <Card title="Affected API routes and screens">
              <ul className="max-h-56 overflow-y-auto text-xs">{a.affected_routes.map((r) => <li key={r} className="font-mono">{r}</li>)}</ul>
              <p className="label mt-3">Frontend files calling those routes</p>
              <ul className="text-xs">{a.affected_frontend.map((f) => <li key={f.file}>{f.file} <span className="text-faint">({f.calls.join(", ")})</span></li>)}</ul>
            </Card>
          </div>
        </>
      )}
      <Card title="Requirements traceability" subtitle={`${tr.data?.data.project ?? ""} · synthetic requirement IDs mapped to real modules and tests`}>
        <DataTable rows={(tr.data?.data.requirements ?? []).map((r) => ({ id: r.id, title: r.title, status: r.status, modules: r.modules.join(", "),
          verification: r.verification.map((v) => `${v.file}${v.exists ? "" : " (MISSING)"}`).join(", ") }))}
          columns={[{ key: "id", label: "Requirement" }, { key: "title", label: "Title" }, { key: "status", label: "Status" }, { key: "modules", label: "Modules" }, { key: "verification", label: "Verification evidence" }]} />
      </Card>
      <Card title="Configuration change comparison">
        <div className="grid gap-2 md:grid-cols-2">
          <textarea className="input font-mono text-xs" rows={4} value={before} onChange={(e) => setBefore(e.target.value)} aria-label="Before configuration" />
          <textarea className="input font-mono text-xs" rows={4} value={after} onChange={(e) => setAfter(e.target.value)} aria-label="After configuration" />
        </div>
        <button className="btn btn-ghost mt-2" onClick={() => cmp.mutate()}>Compare</button>
        {cmp.error ? <ErrorBox error={cmp.error} /> : null}
        {cmp.data && <DataTable rows={cmp.data.data.changes.map((c) => ({ ...c, before: JSON.stringify(c.before), after: JSON.stringify(c.after) }))}
          columns={[{ key: "key", label: "Key" }, { key: "kind", label: "Change" }, { key: "before", label: "Before" }, { key: "after", label: "After" }, { key: "risk", label: "Risk" }]} />}
      </Card>
    </div>
  );
}
