import { useEffect, useId, useState } from "react";

import { Alert, Json, Pill, Stat } from "./ui";

// --------------------------------------------------------------------------- Mermaid
export function ArchitectureDiagram({ code, title }: { code: string; title?: string }) {
  const id = `m${useId().replace(/:/g, "")}`;
  const [svg, setSvg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const mermaid = (await import("mermaid")).default;
        mermaid.initialize({ startOnLoad: false, securityLevel: "strict", theme: "base",
          themeVariables: { primaryColor: "#E8F1FB", primaryBorderColor: "#1565C0", primaryTextColor: "#17324D", lineColor: "#00897B", fontFamily: "Inter, system-ui, sans-serif" } });
        const { svg } = await mermaid.render(id, code);
        if (alive) setSvg(svg);
      } catch (e) {
        if (alive) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => { alive = false; };
  }, [code, id]);
  return (
    <figure className="overflow-x-auto">
      {title && <figcaption className="mb-2 text-sm font-semibold">{title}</figcaption>}
      {svg ? <div className="min-w-[320px] [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full" dangerouslySetInnerHTML={{ __html: svg }} /> : err ? <><Alert tone="warn">Diagram could not render: {err}</Alert><pre className="code mt-2">{code}</pre></> : <div className="muted">Rendering diagram…</div>}
      <details className="mt-2 text-xs"><summary className="cursor-pointer text-brand">Mermaid source</summary><pre className="code mt-1">{code}</pre></details>
    </figure>
  );
}

// --------------------------------------------------------------------------- timeline
export interface StageLog { stage: string; index: number; title: string; agent: string; status: string; summary: string; duration_ms: number }

export function SDLCStageTimeline({ stages, log, pausedAt }: { stages: { stage: string; index: number; title: string; agent: string }[]; log: StageLog[]; pausedAt: string[] }) {
  const by: Record<string, StageLog> = {};
  for (const l of log) by[l.stage] = l;
  return (
    <ol className="grid gap-2 md:grid-cols-3 xl:grid-cols-5" aria-label="AI-SDLC stages">
      {stages.map((s) => {
        const l = by[s.stage];
        const paused = pausedAt.includes(s.stage);
        const st = paused ? "awaiting" : l?.status ?? "pending";
        const cls = st === "completed" ? "border-green-200 bg-green-50" : st === "failed" ? "border-red-200 bg-red-50" : st === "awaiting" || st === "awaiting_approval" ? "border-amber-300 bg-amber-50 node-running" : st === "skipped" ? "border-slate-100 bg-slate-50" : "border-slate-200 bg-white";
        return (
          <li key={s.stage} className={`rounded-xl border p-3 ${cls}`}>
            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-500"><span>Stage {s.index}</span><span>{st === "awaiting" ? "⏸ human decision" : st}</span></div>
            <div className="text-sm font-semibold">{s.title}</div>
            <div className="text-[11px] text-slate-500">{s.agent}</div>
            {l?.summary && <p className="mt-1 line-clamp-4 text-xs text-slate-700" title={l.summary}>{l.summary}</p>}
          </li>
        );
      })}
    </ol>
  );
}

// --------------------------------------------------------------------------- requirements
export function RequirementsViewer({ analysis }: { analysis: any }) {
  if (!analysis) return null;
  return (
    <div className="space-y-4 text-sm">
      <div className="flex flex-wrap items-center gap-2"><Pill tone="brand">{analysis.id}</Pill><Pill tone={analysis.status === "READY_FOR_DESIGN" ? "ok" : "warn"}>{analysis.status}</Pill><span className="text-xs text-slate-500">{analysis.method}</span></div>
      <div>
        <div className="label">Open questions (ambiguities)</div>
        <ul className="space-y-1">{analysis.ambiguities.map((q: any) => <li key={q.id} className="flex items-start gap-2"><Pill tone={q.blocking ? "danger" : "slate"}>{q.blocking ? "blocking" : "open"}</Pill><span>{q.question}</span></li>)}</ul>
      </div>
      <div>
        <div className="label">User stories</div>
        <ul className="list-inside list-disc space-y-1">{analysis.user_stories.map((u: any) => <li key={u.id}><span className="font-mono text-xs text-slate-500">{u.id}</span> {u.story}</li>)}</ul>
      </div>
      <div>
        <div className="label">Acceptance criteria</div>
        <div className="grid gap-2 md:grid-cols-2">{analysis.acceptance_criteria.map((c: any) => <pre key={c.id} className="code"><b>{c.id}</b>{"\n"}{c.gherkin}</pre>)}</div>
      </div>
      <div><div className="label">Dependencies</div><div className="flex flex-wrap gap-1">{analysis.dependencies.map((d: string) => <Pill key={d}>{d}</Pill>)}</div></div>
    </div>
  );
}

// --------------------------------------------------------------------------- tests
export function TestExecutionPanel({ report }: { report: any }) {
  if (!report) return null;
  return (
    <div>
      <div className="mb-3 grid grid-cols-2 gap-2 md:grid-cols-4">
        <Stat label="Build" value={report.build_version} hint={report.status_mapping} />
        <Stat label="Executed" value={report.executed} />
        <Stat label="Passed" value={report.passed} tone="ok" />
        <Stat label="Failed" value={report.failed} tone={report.failed ? "danger" : "ok"} hint={`${report.duration_ms} ms`} />
      </div>
      <div className="max-h-[420px] overflow-auto rounded-xl border border-slate-200">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-canvas text-left text-xs uppercase text-slate-500"><tr><th className="p-2">ID</th><th>Scenario</th><th>Category</th><th>Req</th><th>Result</th></tr></thead>
          <tbody>
            {report.results.map((r: any) => (
              <tr key={r.id} className={`border-t border-slate-100 ${r.passed ? "" : "bg-red-50"}`}>
                <td className="p-2 font-mono text-xs">{r.id}</td>
                <td>{r.title}<div className="text-xs text-slate-500">{r.error || r.detail}</div></td>
                <td><Pill>{r.category}</Pill></td><td className="font-mono text-[11px]">{r.requirement}</td>
                <td>{r.passed ? <span className="font-semibold text-ok">PASS</span> : <span className="font-semibold text-danger">FAIL</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">Executed {report.executed_at} against the reproducible synthetic fixture (clock {report.fixture_clock}).</p>
    </div>
  );
}

// --------------------------------------------------------------------------- security
export function SecurityDashboard({ scan }: { scan: any }) {
  if (!scan) return null;
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        <Stat label="Open findings" value={scan.open_findings} tone={scan.open_findings ? "danger" : "ok"} />
        <Stat label="Files scanned" value={scan.secret_scan.scanned_files} hint={`${scan.secret_scan.findings.length} secret findings`} />
        <Stat label="Frontend bundle" value={scan.frontend_bundle.checked ? `${scan.frontend_bundle.findings.length} keys` : "not built"} tone={scan.frontend_bundle.findings?.length ? "danger" : "ok"} />
        <Stat label="Prompt injection" value={`${scan.prompt_injection.passed}/${scan.prompt_injection.executed}`} />
        <Stat label="Authorization" value={scan.authorization.passed ? "pass" : "FAIL"} tone={scan.authorization.passed ? "ok" : "danger"} />
      </div>
      <Alert tone={scan.dependencies.vulnerability_scan.ran ? "info" : "warn"} title="Dependency scanning">
        {scan.dependencies.packages} packages inventoried. {scan.dependencies.vulnerability_scan.ran ? "pip-audit executed." : scan.dependencies.vulnerability_scan.reason}
      </Alert>
      {scan.secret_scan.findings.length > 0 && <Json value={scan.secret_scan.findings} />}
      <details><summary className="cursor-pointer text-sm text-brand">Prompt-injection probes</summary>
        <ul className="mt-1 text-xs">{scan.prompt_injection.results.map((r: any, i: number) => <li key={i}>{r.detected === r.expected ? "✓" : "✕"} <span className="font-mono">{r.probe}</span></li>)}</ul>
      </details>
    </div>
  );
}

// --------------------------------------------------------------------------- RCA
export function RootCauseExplorer({ rca }: { rca: any }) {
  if (!rca?.hypotheses) return null;
  return (
    <div className="space-y-3 text-sm">
      {rca.confirmed ? <Alert tone="ok" title="Root cause confirmed with evidence">{rca.root_cause}<div className="mt-1 font-mono text-xs">{rca.component}</div></Alert>
        : <Alert tone="warn" title="No root cause confirmed">Insufficient evidence; hypotheses remain open.</Alert>}
      <div>
        <div className="label">Hypotheses</div>
        <ul className="space-y-1">{rca.hypotheses.map((h: any) => <li key={h.id} className="rounded-lg border border-slate-200 p-2"><Pill tone={h.status === "CONFIRMED" ? "ok" : h.status === "REJECTED" ? "slate" : "warn"}>{h.status}</Pill> <b>{h.id}</b> {h.statement}<div className="text-xs text-slate-600">{h.reasoning}</div></li>)}</ul>
      </div>
      <div>
        <div className="label">Evidence</div>
        {rca.evidence.map((e: any, i: number) => (
          <details key={i} className="rounded-lg border border-slate-200 p-2" open={e.type === "code_diff"}>
            <summary className="cursor-pointer"><Pill tone="brand">{e.type}</Pill> {e.detail}</summary>
            {e.diff && <pre className="code mt-2">{e.diff}</pre>}
            {e.failing && <ul className="ml-4 mt-1 list-disc text-xs">{e.failing.map((f: string) => <li key={f}>{f}</li>)}</ul>}
            {e.samples && <Json value={e.samples} />}
          </details>
        ))}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- telemetry
export function TelemetryDashboard({ t }: { t: any }) {
  if (!t) return null;
  const m = t.measured;
  const s = t.synthetic;
  const v = (x: any, k = "mean", d = 1) => (x && x.count ? Number(x[k]).toFixed(d) : "—");
  return (
    <div className="space-y-4">
      <div>
        <div className="label">Measured in this process (last {t.window_minutes} min)</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-6">
          <Stat label="Search latency p95" value={`${v(m.workflow_latency_ms, "p95", 0)} ms`} hint={`${m.workflow_latency_ms?.count ?? 0} workflows`} />
          <Stat label="API latency mean" value={`${v(m.http_latency_ms, "mean", 1)} ms`} hint={`${m.http_latency_ms?.count ?? 0} requests`} />
          <Stat label="Agent success" value={m.agent_success?.count ? `${(m.agent_success.mean * 100).toFixed(1)}%` : "—"} tone="ok" />
          <Stat label="Tool success" value={m.tool_call?.count ? `${(m.tool_call.mean * 100).toFixed(1)}%` : "—"} />
          <Stat label="Verification rate" value={m.verification_rate?.count ? `${(m.verification_rate.mean * 100).toFixed(0)}%` : "—"} hint="verified / evaluated" />
          <Stat label="Data age (median)" value={`${v(m.data_age_hours_median, "mean", 1)} h`} />
          <Stat label="Retries" value={m.retries?.count ?? 0} />
          <Stat label="Booking handoffs" value={m.booking_handoff?.count ?? 0} hint="handoff ≠ booked appointment" />
          <Stat label="Avg days saved" value={v(m.days_saved, "mean", 0)} hint="verified alternatives only" tone="teal" />
          <Stat label="LLM tokens" value={m.llm_tokens?.sum ?? 0} hint={t.llm.configured ? "real usage" : "LLM not configured"} />
          <Stat label="Pending approvals" value={t.pending_approvals} tone="warn" />
          <Stat label="Open anomalies" value={t.anomalies_open} tone={t.anomalies_open ? "danger" : "ok"} />
        </div>
      </div>
      <div>
        <div className="label">Synthetic simulation telemetry <Pill tone="warn">SYNTHETIC</Pill></div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <Stat label="Misclassification rate" value={s.sim_misclassification_rate?.count ? `${(s.sim_misclassification_rate.mean * 100).toFixed(2)}%` : "—"} />
          <Stat label="Unverified shown as confirmed" value={s.sim_unverified_as_confirmed?.sum ?? 0} tone={s.sim_unverified_as_confirmed?.sum ? "danger" : "ok"} />
          <Stat label="Simulated API failure" value={s.sim_api_failure?.count ? `${(s.sim_api_failure.mean * 100).toFixed(1)}%` : "—"} />
          <Stat label="Simulated searches" value={s.sim_confirmed_results?.count ?? 0} />
        </div>
      </div>
      <div>
        <div className="label">Infrastructure (measured)</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
          <Stat label="Process RSS" value={`${t.infrastructure.process_rss_mb ?? "—"} MB`} />
          <Stat label="Load avg (1m)" value={t.infrastructure.load_avg_1m ?? "—"} hint={`${t.infrastructure.cpu_count ?? "?"} CPUs`} />
          <Stat label="Host memory free" value={`${t.infrastructure.host_mem_available_mb ?? "—"} MB`} />
          <Stat label="Disk free" value={`${t.infrastructure.disk_free_gb ?? "—"} GB`} />
          <Stat label="Workflows (DB)" value={t.workflows_total} />
        </div>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- release
export function ReleaseApprovalPanel({ release, approvalId, canApprove, onDecide, busy }: { release: any; approvalId: string | null; canApprove: boolean; onDecide: (d: "APPROVED" | "REJECTED") => void; busy?: boolean }) {
  if (!release?.checklist) return null;
  return (
    <div className="space-y-3 text-sm">
      <div className="flex flex-wrap items-center gap-2"><Pill tone="brand">Release {release.version}</Pill><Pill tone={release.ready ? "ok" : "danger"}>{release.ready ? "checklist passed" : "blocked"}</Pill>{release.decision && <Pill tone={release.decision === "APPROVED" ? "ok" : "danger"}>{release.decision} by {release.decided_by}</Pill>}</div>
      <ul className="space-y-1">{release.checklist.map((c: any) => <li key={c.item} className="flex items-start gap-2"><span className={c.passed ? "text-ok" : "text-danger"}>{c.passed ? "✓" : "✕"}</span><span><b>{c.item}</b> — <span className="text-slate-600">{c.evidence}</span></span></li>)}</ul>
      <details><summary className="cursor-pointer text-brand">Manifest, rollback &amp; migration plan</summary><Json value={{ manifest: release.manifest, rollback_plan: release.rollback_plan, migration_plan: release.migration_plan }} /></details>
      {approvalId && !release.decision && (
        canApprove ? (
          <div className="flex gap-2"><button className="btn-danger" disabled={busy} onClick={() => onDecide("REJECTED")}>Reject release</button><button className="btn-teal" disabled={busy} onClick={() => onDecide("APPROVED")}>Approve production deployment</button></div>
        ) : <Alert tone="info">Waiting for a release approver. Separation of duties: the engineer who started the run cannot approve it. Sign in as “Demo Release Approver”.</Alert>
      )}
    </div>
  );
}
