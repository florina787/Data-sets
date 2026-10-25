import { useMutation } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Download, FileText, Lightbulb, Play, ShieldAlert, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { download, post } from "@/lib/api";
import { fmt, miniMarkdown } from "@/lib/format";
import type { Block, Citation, Decision, Recommendation, RoadmapPhase } from "@/lib/types";
import { ApprovalQueue } from "./Approvals";
import { Chart } from "./Chart";
import { DataTable } from "./DataTable";
import { DependencyGraph } from "./DependencyGraph";
import { Badge, Card, ErrorBox, Kpi } from "./ui";

export function Markdown({ text }: { text: string }) {
  return <div className="prose-ff text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: miniMarkdown(text) }} />;
}

export function Citations({ items }: { items: Citation[] }) {
  return (
    <div className="grid gap-2 md:grid-cols-2" data-testid="citations">
      {items.map((c) => (
        <div key={c.doc_id} className="rounded-lg border border-token p-2.5 text-xs">
          <div className="flex flex-wrap items-center gap-1.5">
            <BookOpen className="h-3.5 w-3.5 text-purple dark:text-lavender" aria-hidden />
            <span className="font-semibold">{c.doc_id}</span>
            <span>rev {c.revision}</span>
            <Badge tone={c.classification === "RESTRICTED" ? "red" : c.classification === "UNKNOWN" ? "amber" : "purple"}>{c.classification}</Badge>
            {c.authoritative ? <Badge tone="teal">authoritative</Badge> : <Badge tone="amber">not authoritative</Badge>}
            {c.flags.map((f) => (
              <Badge key={f} tone={f.includes("injection") ? "red" : "amber"}>
                {f.replace(/_/g, " ")}
              </Badge>
            ))}
          </div>
          <div className="mt-1 font-medium">{c.title}</div>
          <div className="muted mt-0.5">
            Effective {c.effective_date} · review due {c.review_due} · {c.source} · provenance {c.provenance_sha256 ? c.provenance_sha256.slice(0, 10) + "..." : "missing"}
          </div>
          <div className="mt-1 italic">"{c.snippet}"</div>
        </div>
      ))}
    </div>
  );
}

export function DecisionList({ decisions }: { decisions: Decision[] }) {
  return (
    <div className="max-h-72 space-y-1 overflow-auto" data-testid="policy-decisions">
      {decisions.map((d) => (
        <details key={d.id} className="rounded border border-token px-2 py-1 text-xs">
          <summary className="flex cursor-pointer flex-wrap items-center gap-1.5">
            <Badge tone={d.decision === "ALLOW" ? "teal" : "red"}>{d.decision}</Badge>
            <span className="font-semibold">{d.policy_id}</span>
            <span>{d.action}</span>
            <span className="muted truncate">{d.tool ?? d.resource}</span>
            <span className="muted ml-auto">{d.actor}</span>
          </summary>
          <div className="mt-1">{d.reason}</div>
          <ol className="mt-1 space-y-0.5">
            {d.checks.map((c, i) => (
              <li key={i} className="flex gap-1.5">
                <Badge tone={c.result === "pass" ? "teal" : "red"}>{c.result}</Badge>
                <span className="font-medium">{c.policy_id}</span>
                <span className="muted">{c.detail}</span>
              </li>
            ))}
          </ol>
        </details>
      ))}
    </div>
  );
}

function RecommendationCard({ r }: { r: Recommendation }) {
  return (
    <details className="rounded-lg border border-token p-3 text-xs" open={r.id === "R1"}>
      <summary className="flex cursor-pointer flex-wrap items-center gap-2">
        <span className="font-semibold">
          {r.id} · {r.title}
        </span>
        <Badge tone={r.applies ? "teal" : "amber"}>{r.applies ? "applicable" : "conditional"}</Badge>
        <Badge tone={r.migration_risk === "high" ? "red" : r.migration_risk === "medium" ? "amber" : "teal"}>risk {r.migration_risk}</Badge>
        <Badge tone="purple">confidence {Math.round(r.confidence * 100)}%</Badge>
      </summary>
      <div className="mt-2 grid gap-2 md:grid-cols-2">
        <div><b>Why:</b> {r.why}</div>
        <div><b>Security classification:</b> {r.security_classification}</div>
        <div><b>Prerequisites:</b> {r.prerequisites.join("; ")}</div>
        <div><b>Evidence:</b> {r.evidence.join("; ") || "-"}</div>
        <div><b>Steps:</b> {r.implementation_steps.join(" → ")}</div>
        <div><b>Rollback:</b> {r.rollback}</div>
        <div><b>Test plan:</b> {r.test_plan.join("; ")}</div>
        <div><b>Effort (assumption):</b> {r.effort_assumption}</div>
        <div><b>Trade-offs:</b> {r.tradeoffs}</div>
        <div><b>Human decisions:</b> {r.human_decisions.join("; ")}</div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1" aria-label="Pattern diagram">
        {r.diagram.nodes.map((n, i) => (
          <span key={i} className="flex items-center gap-1">
            <span className="rounded-md border border-token bg-[var(--panel-2)] px-2 py-0.5">{n}</span>
            {i < r.diagram.nodes.length - 1 && <span aria-hidden>→</span>}
          </span>
        ))}
      </div>
    </details>
  );
}

export function Roadmap({ items }: { items: RoadmapPhase[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-3" data-testid="roadmap">
      {items.map((p) => (
        <div key={p.phase} className="rounded-lg border border-token p-3 text-xs">
          <div className="font-semibold text-purple dark:text-lavender">{p.phase}</div>
          <div className="muted">Owner: {p.owner}</div>
          <ul className="mt-1 list-disc pl-4">
            {p.items.map((i) => (
              <li key={i}>{i}</li>
            ))}
          </ul>
          <div className="mt-1"><b>Depends on:</b> {p.dependencies.join(", ")}</div>
          <div><b>Exit:</b> {p.exit}</div>
        </div>
      ))}
    </div>
  );
}

function ScenarioControls({ inputs }: { inputs: Record<string, unknown> }) {
  const [delays, setDelays] = useState(((inputs.delays_hours as number[]) ?? [24, 48]).join(", "));
  const [low, setLow] = useState(Number(inputs.downtime_cost_per_hour_low ?? 4000));
  const [high, setHigh] = useState(Number(inputs.downtime_cost_per_hour_high ?? 9000));
  const [install, setInstall] = useState(Number(inputs.install_hours ?? 9));
  const m = useMutation({
    mutationFn: () =>
      post<{ scenarios: { delay_hours: number; downtime_hours: number; cost_low_usd: number; cost_high_usd: number; slot_start: string; monte_carlo: { p90_hours: number } | null }[] }>(
        "/api/simulations/compare",
        { ...inputs, delays_hours: delays.split(/[,\s]+/).filter(Boolean).map(Number), downtime_cost_per_hour_low: low, downtime_cost_per_hour_high: high, install_hours: install },
      ),
  });
  const sc = m.data?.data.scenarios;
  return (
    <Card title="Change assumptions and recompute" subtitle="Deterministic: identical inputs always return identical results." className="!p-3">
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="flex flex-col gap-1">Part delays (h)<input className="input w-36" value={delays} onChange={(e) => setDelays(e.target.value)} aria-label="Part delays in hours" /></label>
        <label className="flex flex-col gap-1">Cost/h low ($)<input className="input w-28" type="number" value={low} onChange={(e) => setLow(Number(e.target.value))} /></label>
        <label className="flex flex-col gap-1">Cost/h high ($)<input className="input w-28" type="number" value={high} onChange={(e) => setHigh(Number(e.target.value))} /></label>
        <label className="flex flex-col gap-1">Install hours<input className="input w-24" type="number" value={install} onChange={(e) => setInstall(Number(e.target.value))} /></label>
        <button className="btn btn-primary" onClick={() => m.mutate()} disabled={m.isPending} data-testid="recompute">
          <Play className="h-4 w-4" /> Recompute
        </button>
      </div>
      {m.error && <div className="mt-2"><ErrorBox error={m.error} /></div>}
      {sc && (
        <div className="mt-3 grid gap-3 md:grid-cols-2" data-testid="recomputed">
          <Chart title="Recomputed downtime" spec={{ kind: "bar", x: sc.map((s) => `${s.delay_hours} h`), series: [{ name: "Downtime (h)", data: sc.map((s) => s.downtime_hours) }, { name: "P90 (h)", data: sc.map((s) => s.monte_carlo?.p90_hours ?? null) }] }} height={220} />
          <DataTable columns={[{ key: "delay_hours", label: "Delay h" }, { key: "slot_start", label: "Slot" }, { key: "downtime_hours", label: "Downtime h" }, { key: "cost_low_usd", label: "Cost low $" }, { key: "cost_high_usd", label: "Cost high $" }]} rows={sc} />
        </div>
      )}
    </Card>
  );
}

function RoiControls({ inputs }: { inputs: Record<string, unknown> }) {
  const editable = ["manual_hours_per_month", "loaded_labor_cost_per_hour", "automation_fraction_low", "automation_fraction_high", "downtime_reduction_low", "downtime_reduction_high", "downtime_cost_per_hour", "avoided_rework_per_year", "pilot_engineering_cost", "annual_run_cost"];
  const [vals, setVals] = useState<Record<string, number>>(Object.fromEntries(editable.map((k) => [k, Number(inputs[k])])));
  const m = useMutation({ mutationFn: () => post<{ annual_benefit: { low: { total: number }; high: { total: number } }; first_year_cost: number; payback_months: { low_case: number | null; high_case: number | null } }>("/api/simulations/roi", vals) });
  const r = m.data?.data;
  return (
    <Card title="Editable ROI assumptions" subtitle="Every figure is an assumption until validated with customer data." className="!p-3">
      <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-5">
        {editable.map((k) => (
          <label key={k} className="flex flex-col gap-1">
            {k.replace(/_/g, " ")}
            <input className="input" type="number" step="any" value={vals[k]} onChange={(e) => setVals({ ...vals, [k]: Number(e.target.value) })} />
          </label>
        ))}
      </div>
      <button className="btn btn-primary mt-2" onClick={() => m.mutate()} disabled={m.isPending} data-testid="roi-recompute">
        <Play className="h-4 w-4" /> Recompute ROI
      </button>
      {m.error && <div className="mt-2"><ErrorBox error={m.error} /></div>}
      {r && (
        <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4" data-testid="roi-result">
          <Kpi label="Benefit low" value={`$${r.annual_benefit.low.total.toLocaleString()}`} />
          <Kpi label="Benefit high" value={`$${r.annual_benefit.high.total.toLocaleString()}`} />
          <Kpi label="First-year cost" value={`$${r.first_year_cost.toLocaleString()}`} />
          <Kpi label="Payback (mo)" value={`${fmt(r.payback_months.high_case)} - ${fmt(r.payback_months.low_case)}`} />
        </div>
      )}
    </Card>
  );
}

type TestResult = { passed: number; failed: number; exit_code: number; duration_s: number; tests: { name: string; status: string; time_s: number; message: string }[]; sandbox: string };

export function BridgeTestRunner({ bundleId }: { bundleId: string }) {
  const m = useMutation({ mutationFn: () => post<TestResult>("/api/bridge/test", { bundle_id: bundleId }) });
  const r = m.data?.data;
  return (
    <Card title="Run generated contract, security and MCP tests" subtitle="Executes the bundle's pytest suite in a subprocess sandbox (minimal env, no proxies, timeout)." className="!p-3">
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={() => m.mutate()} disabled={m.isPending} data-testid="run-bridge-tests">
          <Play className="h-4 w-4" /> {m.isPending ? "Running tests..." : "Run tests"}
        </button>
        <button className="btn btn-ghost" onClick={() => download(`/api/bridge/${bundleId}/download`, `${bundleId}.zip`)}>
          <Download className="h-4 w-4" /> Download bundle
        </button>
      </div>
      {m.error && <div className="mt-2"><ErrorBox error={m.error} /></div>}
      {r && (
        <div className="mt-3 space-y-2" data-testid="bridge-test-result">
          <div className="flex flex-wrap gap-2">
            <Badge tone={r.failed === 0 && r.exit_code === 0 ? "teal" : "red"}>{r.passed} passed</Badge>
            <Badge tone={r.failed ? "red" : "gray"}>{r.failed} failed</Badge>
            <Badge tone="gray">{r.duration_s}s</Badge>
            <span className="muted text-xs">{r.sandbox}</span>
          </div>
          <DataTable columns={[{ key: "name", label: "Test" }, { key: "status", label: "Status" }, { key: "time_s", label: "Seconds" }, { key: "message", label: "Message" }]} rows={r.tests} maxHeight={260} />
        </div>
      )}
    </Card>
  );
}

export function Workspace({ blocks, onQuery, runId }: { blocks: Block[]; onQuery?: (q: string) => void; runId?: string }) {
  const navigate = useNavigate();
  const [exportError, setExportError] = useState<unknown>(null);
  const exportRun = async (fmtName: string) => {
    if (!runId) return;
    try {
      setExportError(null);
      const r = await post<{ download: string; id: string }>("/api/reports/generate", { kind: "workspace", fmt: fmtName, run_id: runId });
      await download(r.data.download, `workspace.${fmtName}`);
    } catch (e) {
      setExportError(e);
    }
  };
  return (
    <div className="space-y-3" data-testid="workspace">
      {blocks.map((b, i) => {
        switch (b.type) {
          case "answer":
            return (
              <Card key={i} className="border-l-4 !border-l-purple">
                <Markdown text={b.markdown} />
              </Card>
            );
          case "kpis":
            return (
              <div key={i} className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-5">
                {b.items.map((k) => (
                  <Kpi key={k.label} {...k} value={fmt(k.value)} />
                ))}
              </div>
            );
          case "chart":
            return (
              <Card key={i} title={b.title} subtitle={[b.caption, b.source && `Source: ${b.source}`].filter(Boolean).join(" · ")}>
                <Chart spec={b.chart} title={b.title} />
              </Card>
            );
          case "table":
            return (
              <Card key={i} title={b.title} subtitle={b.caption}>
                <DataTable columns={b.columns} rows={b.rows} label={b.title} />
              </Card>
            );
          case "citations":
            return (
              <Card key={i} title={`Citations (${b.items.length})`} subtitle="Filtered by classification and role before ranking. Revision, date and provenance shown for each.">
                <Citations items={b.items} />
              </Card>
            );
          case "warnings":
            return (
              <Card key={i} title="Warnings and withheld evidence">
                <ul className="space-y-1 text-xs">
                  {b.items.map((w) => (
                    <li key={w} className="flex gap-2">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber" aria-hidden />
                      {w}
                    </li>
                  ))}
                </ul>
              </Card>
            );
          case "assumptions":
            return (
              <Card key={i} title="Assumptions">
                <ul className="list-disc space-y-0.5 pl-4 text-xs">{b.items.map((a) => <li key={a}>{a}</li>)}</ul>
              </Card>
            );
          case "formulas":
            return (
              <Card key={i} title="Formulas (inspectable)">
                <ul className="space-y-0.5 font-mono text-[11px]">{b.items.map((a) => <li key={a}>{a}</li>)}</ul>
              </Card>
            );
          case "policy":
            return (
              <Card key={i} title="Decision trace" subtitle={`${b.allowed} allowed · ${b.denied} denied by the deterministic policy engine`} actions={<ShieldCheck className="h-4 w-4 text-teal" />}>
                <DecisionList decisions={b.decisions} />
              </Card>
            );
          case "approval":
            return (
              <Card key={i} title="Human approval gate" subtitle="Nothing is written until a different, authorized person approves. Execution re-checks policy and rejects replays.">
                <ApprovalQueue filterIds={b.items.map((a) => a.id)} />
              </Card>
            );
          case "artifacts":
            return (
              <Card key={i} title="Generated artifacts">
                <div className="flex flex-wrap gap-2">
                  {b.items.map((a) =>
                    a.kind === "report" ? (
                      <button key={a.id} className="btn btn-ghost" onClick={() => download(`/api/reports/${a.id}/download`, `${a.id}.${a.fmt}`)}>
                        <FileText className="h-4 w-4" /> {a.title} ({a.fmt})
                      </button>
                    ) : (
                      <button key={a.id} className="btn btn-ghost" onClick={() => navigate(`/bridge?bundle=${a.id}`)}>
                        <FileText className="h-4 w-4" /> {a.title} · {a.id}
                      </button>
                    ),
                  )}
                </div>
              </Card>
            );
          case "actions":
            return (
              <div key={i} className="flex flex-wrap gap-2">
                {b.items.map((a) => (
                  <button
                    key={a.label}
                    className="btn btn-ghost"
                    onClick={() => {
                      if (a.kind === "navigate") navigate(a.target);
                      else if (a.kind === "query") onQuery?.(a.target);
                      else if (a.kind === "export") exportRun(a.target);
                      else if (a.kind === "download") download(a.target, "download").catch(setExportError);
                    }}
                  >
                    <Lightbulb className="h-4 w-4" /> {a.label}
                  </button>
                ))}
                {runId && (
                  <>
                    <button className="btn btn-ghost" onClick={() => exportRun("md")}>
                      <Download className="h-4 w-4" /> Markdown
                    </button>
                    <button className="btn btn-ghost" onClick={() => exportRun("json")}>
                      <Download className="h-4 w-4" /> JSON
                    </button>
                  </>
                )}
                {exportError ? <ErrorBox error={exportError} /> : null}
              </div>
            );
          case "clarify":
            return (
              <Card key={i} title="Try one of these">
                <div className="flex flex-wrap gap-2">
                  {b.suggestions.map((s) => (
                    <button key={s} className="btn btn-ghost text-left !text-xs" onClick={() => onQuery?.(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </Card>
            );
          case "graph":
            return (
              <Card key={i} title={b.title} subtitle="Nodes and edges come from parsed metadata. Dashed nodes are unknowns.">
                <DependencyGraph nodes={b.nodes} edges={b.edges} height={380} />
              </Card>
            );
          case "recommendations":
            return (
              <Card key={i} title="Modernization options (evidence-backed)">
                <div className="space-y-2">{b.items.map((r) => <RecommendationCard key={r.id} r={r} />)}</div>
              </Card>
            );
          case "roadmap":
            return (
              <Card key={i} title="Phased 30/60/90-day roadmap">
                <Roadmap items={b.items} />
              </Card>
            );
          case "scenario_controls":
            return <ScenarioControls key={i} inputs={b.inputs} />;
          case "roi_controls":
            return <RoiControls key={i} inputs={b.inputs} />;
          case "code":
            return (
              <Card key={i} title={b.title} subtitle="Preview only - not executed until you run the tests.">
                <pre className="max-h-80 overflow-auto rounded-lg bg-navy p-3 text-[11px] text-offwhite">{b.code}</pre>
              </Card>
            );
          case "bridge_test":
            return <BridgeTestRunner key={i} bundleId={b.bundle_id} />;
          case "decision_trace":
            return (
              <Card key={i} title="Deterministic decision trace" actions={<ShieldAlert className="h-4 w-4 text-blocked" />}>
                <div className="grid gap-2 text-xs md:grid-cols-4">
                  <div><b>Identity:</b> {b.identity.id} ({b.identity.role}, {b.identity.org})</div>
                  <div><b>Classification:</b> {b.classification}</div>
                  <div><b>Destination:</b> {b.destination}</div>
                  <div><b>Decision:</b> <Badge tone="red">{b.decision.decision}</Badge> {b.decision.policy_id}</div>
                </div>
                <div className="mt-2"><DecisionList decisions={[b.decision]} /></div>
              </Card>
            );
          default:
            return null;
        }
      })}
    </div>
  );
}
