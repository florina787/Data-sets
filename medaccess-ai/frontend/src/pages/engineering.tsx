import { useEffect, useState } from "react";

import {
  ArchitectureDiagram, ReleaseApprovalPanel, RequirementsViewer, RootCauseExplorer, SDLCStageTimeline,
  SecurityDashboard, TelemetryDashboard, TestExecutionPanel,
} from "../components/sdlc";
import { Alert, Card, Empty, ErrorText, Json, PageHeader, Pill, Spinner, Stat, fmtDate } from "../components/ui";
import { useApp } from "../hooks/AppContext";
import { useAsync } from "../hooks/useAsync";
import { endpoints, type Approval } from "../services/api";

const RUN_KEY = "medaccess.sdlcRun";
const readRun = () => { try { return sessionStorage.getItem(RUN_KEY); } catch { return null; } };
const writeRun = (v: string) => { try { sessionStorage.setItem(RUN_KEY, v); } catch { /* ignore */ } };

// ----------------------------------------------------------------------------- Command center
export function CommandCenterPage() {
  const { can, user } = useApp();
  const [run, setRun] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [volume, setVolume] = useState(200);
  const [answer, setAnswer] = useState("Only verified appointments from providers meeting the documented eligibility requirements may be presented as confirmed alternatives.");
  const [tab, setTab] = useState("timeline");

  useEffect(() => {
    const id = readRun();
    if (id) endpoints.sdlcRun(id).then(setRun).catch(() => undefined);
  }, []);

  const wrap = async (fn: () => Promise<any>) => {
    setBusy(true); setErr(null);
    try { const r = await fn(); if (r) { setRun(r); writeRun(r.run_id); } } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); }
  };
  const start = () => wrap(() => endpoints.sdlcStart(volume));
  const clarify = () => wrap(async () => (await endpoints.decide(run.approval_id, { decision: "APPROVED", answer }) as any).workflow);
  const release = (decision: "APPROVED" | "REJECTED") => wrap(async () => (await endpoints.decide(run.approval_id, { decision }) as any).workflow);
  const refresh = () => run && wrap(() => endpoints.sdlcRun(run.run_id));

  const pq = run?.pending_question;
  return (
    <div className="space-y-5">
      <PageHeader title="AI-SDLC Command Center" subtitle="The 90-Day MRI Wait-Time Challenge — a separate LangGraph engineering workflow from requirement to post-release monitoring, with two human checkpoints."
        actions={<div className="flex flex-wrap items-end gap-2">
          <label className="text-xs">Simulation volume<input className="input w-28" type="number" min={10} max={2000} value={volume} onChange={(e) => setVolume(Number(e.target.value))} /></label>
          <button className="btn-primary" disabled={busy || !can("sdlc:write")} onClick={start}>{run ? "Restart challenge" : "Start the challenge"}</button>
          {run && <button className="btn-ghost" onClick={refresh} disabled={busy}>Refresh</button>}
        </div>} />
      {!can("sdlc:write") && <Alert tone="info">You are signed in as {user?.name}. You can review runs and approve releases; starting a run requires the engineer role.</Alert>}
      <ErrorText error={err} />
      {busy && <Spinner label="Agents are working…" />}
      {!run ? <Empty>Start the challenge to watch the Requirements, Architecture, Development, QA, Monitoring, RCA and Release agents work through the full lifecycle.</Empty> : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <Stat label="Run" value={<span className="text-base">{run.run_id}</span>} hint={run.status} />
            <Stat label="Stages complete" value={`${new Set(run.stage_log.filter((s: any) => s.status === "completed").map((s: any) => s.stage)).size}/15`} />
            <Stat label="Anomalies detected" value={run.anomalies.length} tone={run.anomalies.length ? "danger" : "ok"} />
            <Stat label="Root cause" value={run.rca?.confirmed ? "confirmed" : "—"} tone={run.rca?.confirmed ? "ok" : "brand"} />
            <Stat label="Production build" value={run.deployment.length ? run.deployment[run.deployment.length - 1].to : "1.4.0"} hint="simulated deployment" />
          </div>
          {pq?.type === "REQUIREMENT_CLARIFICATION" && (
            <Card title="⏸ Human clarification required (Stage 3)">
              <Alert tone="warn" title="Requirements Agent detected an ambiguity">{pq.question}</Alert>
              <ul className="ml-5 mt-2 list-disc text-xs text-slate-600">{pq.all_questions.map((q: string) => <li key={q}>{q}</li>)}</ul>
              <label className="label mt-3" htmlFor="ans">Product owner decision</label>
              <textarea id="ans" className="input h-20" value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={1000} />
              <button className="btn-teal mt-2" disabled={busy || !can("approval:engineering")} onClick={clarify}>Record decision &amp; continue</button>
            </Card>
          )}
          {pq?.type === "PRODUCTION_DEPLOYMENT" && (
            <Card title="⏸ Release approval required (Stage 13)">
              <ReleaseApprovalPanel release={run.release} approvalId={run.approval_id} canApprove={can("approval:release") && user?.id !== run.requested_by} onDecide={release} busy={busy} />
            </Card>
          )}
          {run.status === "COMPLETED" && <Alert tone="ok" title="Lifecycle complete">The defect is absent from the post-release regression dataset: {run.post_release?.simulation?.unverified_presented_as_confirmed} unverified slots presented as confirmed; accuracy {(run.post_release?.simulation?.recommendation_accuracy * 100).toFixed(2)}%.</Alert>}
          <div className="flex flex-wrap gap-1" role="tablist">
            {["timeline", "monitoring", "root cause", "fix & regression", "release", "traceability"].map((t) => (
              <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "btn-primary px-3 py-1" : "btn-ghost px-3 py-1"} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>
          {tab === "timeline" && <Card><SDLCStageTimeline stages={run.stages} log={run.stage_log} pausedAt={run.paused_at} /></Card>}
          {tab === "monitoring" && (
            <Card title="Monitoring Agent — anomalies (synthetic production traffic)">
              {run.anomalies.length ? <div className="space-y-2">{run.anomalies.map((a: any) => (
                <div key={a.id} className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm"><Pill tone="danger">{a.severity}</Pill> <b>{a.rule}</b> · {a.component}<div className="text-xs">{a.evidence}</div><div className="text-xs text-slate-600">Investigate: {a.recommended_investigation}</div></div>))}</div> : <Empty>No anomalies yet.</Empty>}
              {run.production_sim?.searches && <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
                <Stat label="Baseline accuracy" value={`${(run.baseline_sim.recommendation_accuracy * 100).toFixed(1)}%`} tone="ok" />
                <Stat label="1.5.0 accuracy" value={`${(run.production_sim.recommendation_accuracy * 100).toFixed(1)}%`} tone="danger" />
                <Stat label="Unverified shown confirmed" value={run.production_sim.unverified_presented_as_confirmed} tone="danger" />
                <Stat label="Simulated searches" value={run.production_sim.searches} hint="synthetic" />
              </div>}
            </Card>
          )}
          {tab === "root cause" && <Card title="Root Cause Analysis Agent">{run.rca?.hypotheses ? <RootCauseExplorer rca={run.rca} /> : <Empty>Not reached yet.</Empty>}</Card>}
          {tab === "fix & regression" && (
            <Card title="Development Agent fix + QA regression">
              {run.fix?.diff ? <><p className="text-sm font-semibold">{run.fix.change}</p><pre className="code mt-2">{run.fix.diff}</pre></> : <Empty>Not reached yet.</Empty>}
              {run.regression?.fixed && <div className="mt-4 grid gap-4 lg:grid-cols-2"><div><div className="label">Fixed build</div><TestExecutionPanel report={run.regression.fixed} /></div><div><div className="label">Defective build (same tests)</div><TestExecutionPanel report={run.regression.defective} /></div></div>}
            </Card>
          )}
          {tab === "release" && <Card title="Release Agent">{run.release?.checklist ? <ReleaseApprovalPanel release={run.release} approvalId={null} canApprove={false} onDecide={() => undefined} /> : <Empty>Not reached yet.</Empty>}</Card>}
          {tab === "traceability" && <TraceabilityCard runId={run.run_id} />}
        </>
      )}
    </div>
  );
}

function TraceabilityCard({ runId }: { runId: string }) {
  const { data } = useAsync(() => endpoints.sdlcTrace(runId), [runId]);
  return (
    <Card title="Traceability chain — Requirement → Architecture → Code → Test → Release → Monitoring">
      {!data ? <Spinner /> : (
        <ol className="space-y-1 text-sm">{data.chain.map((c: any) => (
          <li key={c.trace_ref} className="flex flex-wrap items-center gap-2"><Pill tone={c.trace_ref.startsWith("REQ") ? "brand" : c.trace_ref.startsWith("TEST") ? "ok" : c.trace_ref.startsWith("MON") ? "danger" : c.trace_ref.startsWith("REL") ? "teal" : "slate"}>{c.trace_ref}</Pill><b>{c.stage}</b><span className="text-slate-600">{c.summary}</span></li>))}
        </ol>
      )}
    </Card>
  );
}

// ----------------------------------------------------------------------------- Requirements
export function RequirementsPage() {
  const { can } = useApp();
  const base = useAsync(() => endpoints.requirements(), []);
  const [text, setText] = useState("Patients should be able to find MRI appointments within 25 km.");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <div className="space-y-5">
      <PageHeader title="Requirements Studio" subtitle="Requirements Agent: user stories, acceptance criteria, dependencies, traceability IDs and the open questions humans must answer." />
      <Card title="Analyze a requirement">
        <textarea className="input h-24" value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} aria-label="Business requirement" />
        <button className="btn-primary mt-2" disabled={!can("sdlc:write")} onClick={async () => { try { setRes(await endpoints.analyze(text)); setErr(null); } catch (e) { setErr(String(e)); } }}>Analyze</button>
        <ErrorText error={err} />
        {res && <div className="mt-4"><RequirementsViewer analysis={res} /></div>}
      </Card>
      {base.data && <Card title="Demo requirement — 90-Day MRI challenge"><p className="mb-3 text-sm">{base.data.demo_requirement}</p><RequirementsViewer analysis={base.data.demo_analysis} /></Card>}
    </div>
  );
}

// ----------------------------------------------------------------------------- Architecture
export function ArchitecturePage() {
  const { data, error } = useAsync(() => endpoints.architecture(), []);
  const [key, setKey] = useState("patient_workflow");
  return (
    <div className="space-y-5">
      <PageHeader title="Architecture Explorer" subtitle="Reproducible Mermaid diagrams generated by the Architecture Agent from the compiled graphs and live registries." />
      <ErrorText error={error} />
      {!data ? <Spinner /> : (
        <>
          <div className="flex flex-wrap gap-1">{Object.entries(data).map(([k, v]: any) => <button key={k} className={key === k ? "btn-primary px-3 py-1" : "btn-ghost px-3 py-1"} onClick={() => setKey(k)}>{v.title}</button>)}</div>
          <Card><ArchitectureDiagram key={key} code={data[key].mermaid} title={data[key].title} /></Card>
        </>
      )}
    </div>
  );
}

// ----------------------------------------------------------------------------- Development
export function DevelopmentPage() {
  const b = useAsync(() => endpoints.builds(), []);
  const [rca, setRca] = useState<any>(null);
  return (
    <div className="space-y-5">
      <PageHeader title="Development Workspace" subtitle="Builds, status-mapping variants and proposed code changes. Code changes stay subject to repository permissions and review." />
      {b.data && (
        <Card title="Builds">
          <div className="grid gap-3 md:grid-cols-3">{Object.values(b.data.builds).map((x: any) => (
            <div key={x.version} className={`rounded-xl border p-3 text-sm ${x.defect_injected ? "border-red-200 bg-red-50" : "border-slate-200"}`}>
              <div className="flex items-center gap-2"><b>{x.version}</b>{x.defect_injected && <Pill tone="danger">controlled defect</Pill>}{Object.entries(b.data.active).filter(([, v]) => v === x.version).map(([env]) => <Pill key={env} tone="teal">{env}</Pill>)}</div>
              <div className="font-mono text-xs">{x.status_mapping}</div><p className="mt-1 text-xs text-slate-600">{x.description}</p>
            </div>))}</div>
          <p className="mt-2 text-xs text-slate-500">{b.data.note}</p>
        </Card>
      )}
      <Card title="Diff a build against the baseline" actions={<button className="btn-primary" onClick={async () => setRca(await endpoints.rca("1.5.0"))}>Analyze build 1.5.0</button>}>
        {rca ? <RootCauseExplorer rca={rca} /> : <p className="muted">Runs the RCA agent's evidence collection: test suite on both builds plus a status-mapping diff.</p>}
      </Card>
    </div>
  );
}

// ----------------------------------------------------------------------------- QA
export function QAPage() {
  const [build, setBuild] = useState("1.4.0");
  const [report, setReport] = useState<any>(null);
  const [sim, setSim] = useState<any>(null);
  const [volume, setVolume] = useState(200);
  const [busy, setBusy] = useState(false);
  const pyt = useAsync(() => endpoints.pytestReport(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="QA & Test Center" subtitle="Executes the QA Agent's scenario suite against a chosen build, imports pytest results and runs synthetic simulations with ground truth." />
      <Card title="Scenario suite" actions={<div className="flex gap-2">
        <select className="input w-32" value={build} onChange={(e) => setBuild(e.target.value)} aria-label="Build">{["1.4.0", "1.5.0", "1.5.1"].map((b) => <option key={b}>{b}</option>)}</select>
        <button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); setReport(await endpoints.runTests(build)); setBusy(false); }}>Run</button></div>}>
        {report ? <TestExecutionPanel report={report} /> : <p className="muted">29 executable scenarios: no availability, duplicates, stale slots, invalid requisition, wrong service, provider outage, radius boundary, timezone/DST, expired slot, unauthorized booking, regression, safety, injection and privacy.</p>}
      </Card>
      <Card title="Automated test report (pytest)">
        {pyt.data?.available ? <div className="grid grid-cols-2 gap-2 md:grid-cols-5"><Stat label="Tests" value={pyt.data.tests} /><Stat label="Passed" value={pyt.data.passed} tone="ok" /><Stat label="Failures" value={pyt.data.failures} tone={pyt.data.failures ? "danger" : "ok"} /><Stat label="Errors" value={pyt.data.errors} /><Stat label="Generated" value={<span className="text-sm">{pyt.data.generated}</span>} /></div>
          : <p className="muted">{pyt.data?.hint ?? "Loading…"}</p>}
      </Card>
      <Card title="Synthetic simulation" actions={<div className="flex gap-2"><input className="input w-28" type="number" min={1} max={5000} value={volume} onChange={(e) => setVolume(Number(e.target.value))} aria-label="Volume" />
        <button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); setSim(await endpoints.simulate({ volume, build_version: build })); setBusy(false); }}>Simulate {build}</button></div>}>
        {sim ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            <Stat label="Searches" value={sim.searches} hint={`${sim.duration_ms} ms`} />
            <Stat label="With eligible alternative" value={sim.searches_with_eligible_alternative} />
            <Stat label="Avg potential days saved" value={sim.avg_potential_days_saved} tone="teal" />
            <Stat label="Verification failures" value={sim.verification_failures} />
            <Stat label="API failures" value={sim.api_failures} hint={`rate ${(sim.api_failure_rate * 100).toFixed(1)}%`} />
            <Stat label="Accuracy vs ground truth" value={`${(sim.recommendation_accuracy * 100).toFixed(2)}%`} tone={sim.recommendation_accuracy < 1 ? "danger" : "ok"} />
            <Stat label="Top-choice accuracy" value={`${(sim.top_choice_accuracy * 100).toFixed(1)}%`} />
            <Stat label="Unverified as confirmed" value={sim.unverified_presented_as_confirmed} tone={sim.unverified_presented_as_confirmed ? "danger" : "ok"} />
          </div>
        ) : <p className="muted">All simulation output is synthetic and labelled as such.</p>}
      </Card>
    </div>
  );
}

// ----------------------------------------------------------------------------- Security & Governance
export function SecurityPage() {
  const [scan, setScan] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const gov = useAsync(() => endpoints.governance(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="Security & Governance" subtitle="Real local checks plus the governance inventory: permissions, versions, approvals, provenance and audit integrity." />
      <Card title="Security Agent scan" actions={<button className="btn-primary" disabled={busy} onClick={async () => { setBusy(true); setScan(await endpoints.securityScan()); setBusy(false); }}>{busy ? "Scanning…" : "Run scan"}</button>}>
        {scan ? <SecurityDashboard scan={scan} /> : <p className="muted">Secret scan, frontend bundle key check, dependency inventory, prompt-injection, data-leakage and authorization suites.</p>}
      </Card>
      {gov.data && (
        <>
          <div className="grid gap-3 md:grid-cols-4">
            <Stat label="Audit chain" value={gov.data.audit_chain.valid ? "valid" : "BROKEN"} tone={gov.data.audit_chain.valid ? "ok" : "danger"} hint={`${gov.data.audit_chain.events} events`} />
            <Stat label="Agents" value={gov.data.agent_permissions.length} />
            <Stat label="Model routing" value={<span className="text-sm">{gov.data.model_versions.router}</span>} hint={gov.data.model_versions.enabled ? "LLM enabled" : "LLM not configured — deterministic"} />
            <Stat label="Workflow versions" value={<span className="text-sm">{Object.values(gov.data.workflow_versions).join(", ")}</span>} />
          </div>
          <Card title="Agent & tool permissions">
            <div className="max-h-96 overflow-auto"><table className="w-full text-xs"><thead className="sticky top-0 bg-white text-left uppercase text-slate-500"><tr><th>Agent</th><th>Workflow</th><th>Allowed tools</th><th>Prompt</th></tr></thead>
              <tbody>{gov.data.agent_permissions.filter((a: any) => ["patient", "sdlc"].includes(a.workflow)).map((a: any) => <tr key={a.agent} className="border-t border-slate-100"><td className="py-1 font-semibold">{a.title}</td><td>{a.workflow}</td><td>{a.tools.join(", ") || "—"}</td><td>{a.prompt_version ?? "—"}</td></tr>)}</tbody></table></div>
          </Card>
          <div className="grid gap-5 xl:grid-cols-2">
            <Card title="Data-source provenance">{gov.data.data_provenance.map((p: any) => <div key={p.id} className="flex justify-between border-t border-slate-100 py-1 text-sm"><span>{p.name}</span><span><Pill>{p.data_mode}</Pill> reliability {p.reliability}</span></div>)}</Card>
            <Card title="MCP servers">{gov.data.mcp_servers.map((s: any) => <div key={s.id} className="border-t border-slate-100 py-1 text-sm"><b>{s.title}</b> <Pill tone={s.status.startsWith("implemented") ? "ok" : "slate"}>{s.status}</Pill><div className="text-xs text-slate-500">{s.tools.map((t: any) => t.name).join(", ") || "no tools"}</div></div>)}</Card>
            <Card title="Role permissions"><Json value={gov.data.role_permissions} /></Card>
            <Card title="Recent approvals & releases">
              <ul className="text-xs">{gov.data.recent_approvals.map((a: any) => <li key={a.id}>{fmtDate(a.created_at)} · {a.action_type} · <b>{a.status}</b> {a.decided_by && `by ${a.decided_by}`}</li>)}</ul>
              <div className="label mt-3">Release history</div><ul className="text-xs">{gov.data.release_history.map((h: any, i: number) => <li key={i}>{h.env}: {h.from} → {h.to} by {h.actor} {h.simulated && "(simulated)"}</li>)}</ul>
            </Card>
          </div>
          <AuditCard />
        </>
      )}
    </div>
  );
}

function AuditCard() {
  const { data } = useAsync(() => endpoints.audit(), []);
  return (
    <Card title="Audit trail (redacted, hash-chained)">
      <div className="max-h-80 overflow-auto"><table className="w-full text-xs"><tbody>{data?.items.map((e: any) => <tr key={e.id} className="border-t border-slate-100"><td className="py-1 pr-2 text-slate-500">{fmtDate(e.created_at)}</td><td className="font-semibold">{e.event_type}</td><td>{e.actor}</td><td className="font-mono text-slate-500">{e.hash}</td></tr>)}</tbody></table></div>
    </Card>
  );
}

// ----------------------------------------------------------------------------- Approvals
export function ApprovalsPage() {
  const { user } = useApp();
  const [status, setStatus] = useState("PENDING");
  const { data, reload, error } = useAsync(() => endpoints.approvals(status), [status]);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const decide = async (a: Approval, decision: "APPROVED" | "REJECTED") => {
    setErr(null);
    try {
      const body: Record<string, unknown> = { decision };
      if (a.action_type === "SEARCH_RADIUS_EXPANSION" && decision === "APPROVED") body.radius_km = a.payload?.options?.[0]?.radius_km;
      await endpoints.decide(a.id, body);
      setMsg(`${a.action_type} ${decision.toLowerCase()}.`);
      void reload();
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <div className="space-y-4">
      <PageHeader title="Human Approval Center" subtitle="Workflows pause here before bookings, data sharing, external messages and production deployments." actions={
        <select className="input w-40" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status filter"><option value="PENDING">Pending</option><option value="APPROVED">Approved</option><option value="REJECTED">Rejected</option><option value="">All</option></select>} />
      {msg && <Alert tone="ok">{msg}</Alert>}
      <ErrorText error={err || error} />
      {!data?.items.length ? <Empty>No {status.toLowerCase() || ""} approvals visible to {user?.name}.</Empty> : data.items.map((a) => (
        <Card key={a.id} title={<span>{a.action_type.replace(/_/g, " ")} <Pill tone={a.status === "PENDING" ? "warn" : a.status === "APPROVED" ? "ok" : "danger"}>{a.status}</Pill></span>}>
          <dl className="grid gap-x-4 gap-y-1 text-sm md:grid-cols-[auto,1fr]">
            <dt className="font-semibold">Requested action</dt><dd>{a.reason}</dd>
            <dt className="font-semibold">Requesting agent</dt><dd>{a.requesting_agent}</dd>
            <dt className="font-semibold">Timestamp</dt><dd>{fmtDate(a.created_at)}</dd>
            <dt className="font-semibold">Potential consequences</dt><dd><ul className="ml-4 list-disc">{a.consequences.map((c) => <li key={c}>{c}</li>)}</ul></dd>
            <dt className="font-semibold">Required approver</dt><dd>{a.required_role}</dd>
          </dl>
          <details className="mt-2"><summary className="cursor-pointer text-sm text-brand">Evidence</summary><Json value={a.evidence} /></details>
          {a.status === "PENDING" && a.action_type !== "REQUIREMENT_CLARIFICATION" && (
            <div className="mt-3 flex gap-2"><button className="btn-danger" onClick={() => void decide(a, "REJECTED")}>Reject</button><button className="btn-teal" onClick={() => void decide(a, "APPROVED")}>Approve</button></div>
          )}
          {a.status === "PENDING" && a.action_type === "REQUIREMENT_CLARIFICATION" && <p className="mt-2 text-xs text-slate-500">Answer this in the AI-SDLC Command Center.</p>}
        </Card>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------- Releases
export function ReleasesPage() {
  const { data, reload } = useAsync(() => endpoints.releases(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="Release Management" subtitle="Release records, manifests and the simulated demo environments. Production deployment always requires an approved request." actions={<button className="btn-ghost" onClick={() => void reload()}>Refresh</button>} />
      {data && <Card title="Environments"><div className="flex flex-wrap gap-3">{Object.entries(data.builds.active).map(([env, v]: any) => <Stat key={env} label={env} value={v} hint="simulated in-process" />)}</div></Card>}
      {!data?.releases.length ? <Empty>No releases yet — run the AI-SDLC challenge.</Empty> : data.releases.map((r: any) => (
        <Card key={r.version} title={<span>Release {r.version} <Pill tone={r.status.startsWith("DEPLOYED") ? "ok" : "warn"}>{r.status}</Pill></span>}>
          <div className="text-sm">Approved by {r.approved_by ?? "—"} · deployed {fmtDate(r.deployed_at)}</div>
          {r.manifest?.checklist && <ReleaseApprovalPanel release={{ ...r.manifest, ready: r.manifest.checklist.every((c: any) => c.passed) }} approvalId={null} canApprove={false} onDecide={() => undefined} />}
        </Card>
      ))}
    </div>
  );
}

// ----------------------------------------------------------------------------- Monitoring / observability / metrics
export function MonitoringPage() {
  const an = useAsync(() => endpoints.anomalies(), []);
  const h = useAsync(() => endpoints.health(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="Production Monitoring" subtitle="Deterministic-threshold anomaly detection over measured and simulated telemetry." actions={<button className="btn-primary" onClick={async () => { await endpoints.detect(); void an.reload(); }}>Run detection now</button>} />
      {h.data && <div className="grid gap-3 md:grid-cols-4"><Stat label="API health" value={h.data.status} tone={h.data.status === "ok" ? "ok" : "danger"} /><Stat label="Database" value={h.data.database} /><Stat label="Data mode" value={h.data.data_mode} /><Stat label="Version" value={h.data.version} /></div>}
      {h.data?.warnings?.length > 0 && <Alert tone="warn" title="Startup configuration warnings"><ul className="ml-4 list-disc">{h.data.warnings.map((w: string) => <li key={w}>{w}</li>)}</ul></Alert>}
      <Card title="Anomalies">
        {!an.data?.items.length ? <Empty>No anomalies detected. Rules: {an.data?.rules.join(", ")}</Empty> : (
          <table className="w-full text-sm"><thead className="text-left text-xs uppercase text-slate-500"><tr><th>Detected</th><th>Rule</th><th>Component</th><th>Severity</th><th>Evidence</th><th>Status</th></tr></thead>
            <tbody>{an.data.items.map((a: any) => <tr key={a.id} className="border-t border-slate-100 align-top"><td className="py-1 text-xs">{fmtDate(a.detected_at)}</td><td className="font-semibold">{a.rule}{a.synthetic_telemetry && <Pill tone="warn">synthetic</Pill>}</td><td>{a.component}</td><td><Pill tone={a.severity === "CRITICAL" ? "danger" : "warn"}>{a.severity}</Pill></td><td className="text-xs">{a.evidence}<div className="text-slate-500">{a.recommended_investigation}</div></td><td><Pill tone={a.resolution_status === "OPEN" ? "danger" : "ok"}>{a.resolution_status}</Pill></td></tr>)}</tbody></table>
        )}
      </Card>
    </div>
  );
}

export function ObservabilityPage() {
  const { data } = useAsync(() => endpoints.telemetry(), []);
  const { lastSearch } = useApp();
  const tb = useAsync(() => endpoints.tokenBenchmark(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="LangSmith Observability" subtitle="Trace correlation and privacy controls for agent tracing. Raw sensitive payloads are never exported by default." />
      {data && (
        <div className="grid gap-3 md:grid-cols-4">
          <Stat label="LangSmith" value={data.tracing.langsmith.configured ? "configured" : "not configured"} tone={data.tracing.langsmith.configured ? "ok" : "warn"} hint={`project ${data.tracing.langsmith.project}`} />
          <Stat label="Payload redaction" value={data.tracing.langsmith.redaction} tone={data.tracing.langsmith.redaction === "enabled" ? "ok" : "danger"} />
          <Stat label="OpenTelemetry" value={data.tracing.opentelemetry.enabled ? "enabled" : "disabled"} />
          <Stat label="LLM" value={data.llm.configured ? "configured" : "deterministic mode"} hint={data.llm.note} />
        </div>
      )}
      {!data?.tracing.langsmith.configured && <Alert tone="info" title="LangSmith is not configured in this environment">Enable LangSmith tracing and provide its API key in the backend environment (see .env.example) to export redacted traces. Tracing has not been verified against a live LangSmith project in this build.</Alert>}
      <Card title="Trace correlation (latest workflow)">
        {lastSearch ? <dl className="grid gap-x-4 gap-y-1 text-sm md:grid-cols-[auto,1fr]"><dt className="font-semibold">LangGraph workflow ID</dt><dd className="font-mono">{lastSearch.workflow_id}</dd><dt className="font-semibold">FastAPI request ID</dt><dd className="font-mono">{lastSearch.request_id ?? "—"}</dd><dt className="font-semibold">OpenTelemetry trace ID</dt><dd className="font-mono">{lastSearch.trace_id ?? "—"}</dd><dt className="font-semibold">LangSmith run</dt><dd>{data?.tracing.langsmith.configured ? "tagged workflow:" + lastSearch.workflow_id : "not exported (not configured)"}</dd><dt className="font-semibold">Tokens / cost</dt><dd>{lastSearch.token_usage} tokens</dd></dl> : <Empty>Run a search to see correlated IDs.</Empty>}
      </Card>
      {tb.data && <Card title="Token optimisation benchmark">
        <div className="grid gap-3 md:grid-cols-3"><Stat label="Baseline payload" value={`${tb.data.baseline_chars} chars`} /><Stat label="Optimised payload" value={`${tb.data.optimized_chars} chars`} /><Stat label="Reduction" value={`${tb.data.savings_pct}%`} tone="teal" /></div>
        <p className="mt-2 text-xs text-slate-500">Measurement: {tb.data.measurement}. Techniques: {tb.data.techniques.join(", ")}. Real token savings are reported only once an LLM is configured.</p>
      </Card>}
    </div>
  );
}

export function MetricsPage() {
  const { data, reload, error } = useAsync(() => endpoints.telemetry(), []);
  return (
    <div className="space-y-5">
      <PageHeader title="System Metrics" subtitle="Measured metrics from this backend process, with simulation telemetry separated and labelled." actions={<button className="btn-ghost" onClick={() => void reload()}>Refresh</button>} />
      <ErrorText error={error} />
      {data ? <TelemetryDashboard t={data} /> : <Spinner />}
      <p className="text-xs text-slate-500">Prometheus exposition: <code>/api/v1/metrics</code>. Grafana dashboard: infrastructure/monitoring/grafana.</p>
    </div>
  );
}

export function AdminPage() {
  const users = useAsync(() => endpoints.users(), []);
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="space-y-5">
      <PageHeader title="Administration" />
      {msg && <Alert tone="ok">{msg}</Alert>}
      <Card title="Demo controls">
        <div className="flex flex-wrap gap-2">
          <button className="btn-ghost" onClick={async () => { const r: any = await endpoints.adminReset(); setMsg(`Demo reset. Builds: ${JSON.stringify(r.builds)}`); }}>Reset demo builds &amp; simulation telemetry</button>
          <button className="btn-ghost" onClick={async () => { const r: any = await endpoints.retention(); setMsg(`Retention run: ${r.search_requests_deleted} old searches deleted.`); }}>Run retention policy</button>
        </div>
      </Card>
      <Card title="Users (synthetic demo accounts)">
        <table className="w-full text-sm"><tbody>{users.data?.items.map((u: any) => <tr key={u.id} className="border-t border-slate-100"><td className="py-1">{u.name}</td><td>{u.email}</td><td><Pill>{u.role}</Pill></td></tr>)}</tbody></table>
      </Card>
    </div>
  );
}
