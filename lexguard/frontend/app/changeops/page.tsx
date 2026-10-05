"use client";

import { useState } from "react";
import { Badge, ErrorBox, Kpi, PageHead, Panel, Spinner, StatusPill } from "@/components/ui";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";

const EXAMPLE = "All AI-generated legal research for external use requires citation verification.";

export default function ChangeOpsPage() {
  const { userId } = useAppState();
  const [text, setText] = useState(EXAMPLE);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const analyze = async () => {
    setBusy(true); setErr(null);
    try { setRes(await api.post("/changeops/analyze", userId, { policy_text: text })); } catch (e) { setErr(e as ApiError); setRes(null); } finally { setBusy(false); }
  };
  const approve = async () => {
    setErr(null);
    try { setRes(await api.post("/changeops/approve", userId, { change_id: res.change_id, policy_text: text })); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="page">
      <PageHead title="ChangeOps · AI Governance SDLC" description="Policy change → impact analysis → affected workflows, practices, providers → configuration → test generation → evaluation → pilot → risk review → human approval → simulated deployment → monitoring." />
      <Panel title="Proposed policy change">
        <form className="stack" onSubmit={(e) => { e.preventDefault(); analyze(); }}>
          <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} aria-label="Policy text" />
          <div className="row"><button className="btn btn-primary" disabled={busy}>Analyse impact</button>{busy && <Spinner />}
            <span className="tiny muted">Parsed by deterministic rules. Unstructured text is returned as NEEDS STRUCTURING, never guessed.</span></div>
        </form>
        <ErrorBox error={err} />
        {err?.status === 403 && <div className="notice" style={{ marginTop: 8 }}>Policy analysis requires AI Governance, Knowledge Lawyer, Partner or Admin; approval requires <strong>Tom Becker — AI Governance</strong>.</div>}
      </Panel>
      {res && res.status === "NEEDS_STRUCTURING" && <div className="status-banner tone-warn" style={{ marginTop: 12 }}>{res.message}</div>}
      {res && res.stages && (<>
        <div className="grid grid-4" style={{ marginTop: 12 }}>
          <Kpi label="Change" value={<span className="mono small">{res.change_id}</span>} hint={res.status} />
          <Kpi label="Affected workflows" value={res.affected_workflows.length} tone="warn" hint={`${res.compliant_workflows.length} already compliant`} />
          <Kpi label="Generated tests" value={res.generated_tests.length} />
          <Kpi label="Change risk" value={res.risk} tone={res.risk === "HIGH" ? "bad" : "warn"} />
        </div>
        <div className="grid grid-2" style={{ marginTop: 12 }}>
          <Panel title="Lifecycle" actions={res.status === "PENDING_APPROVAL" ? <button className="btn btn-primary btn-sm" onClick={approve}>Approve &amp; deploy (simulated)</button> : <StatusPill status="APPROVED" />}>
            <div className="pipeline">{res.stages.map((s: any, i: number) => (
              <div className="pipe-step" key={s.stage}><span className="pipe-dot">{i + 1}</span>
                <div><div className="row"><span className="small strong">{s.stage}</span><StatusPill status={s.status === "COMPLETE" ? "ok" : s.status === "PENDING" || s.status === "NOT STARTED" ? "pending" : s.status} label={s.status} /></div>
                  <div className="tiny muted">{s.detail}</div></div></div>))}</div>
          </Panel>
          <div className="stack">
            <Panel title="Affected workflows" bodyClass="table-wrap">
              <table className="table"><thead><tr><th>Workflow</th><th>Missing gates</th><th>Providers / prompts</th></tr></thead>
                <tbody>{res.affected_workflows.map((w: any) => <tr key={w.workflow_id}><td><div className="small strong">{w.name}</div><div className="tiny mono muted">{w.workflow_id} · {w.status}</div></td>
                  <td>{w.missing_gates.map((g: string) => <Badge key={g} tone="warn">+ {g}</Badge>)}</td><td className="tiny">{w.providers.join(", ")}<br />{w.prompts.join(", ")}</td></tr>)}
                  {res.compliant_workflows.map((w: any) => <tr key={w.workflow_id}><td><div className="small">{w.name}</div><div className="tiny mono muted">{w.workflow_id}</div></td>
                    <td><Badge tone="good">already compliant</Badge></td><td className="tiny">{w.providers.join(", ")}</td></tr>)}</tbody></table>
            </Panel>
            <Panel title="Affected practices & providers"><div className="row">{res.affected_practices.map((p: string) => <Badge key={p} tone="info">{p}</Badge>)}</div>
              <div className="row" style={{ marginTop: 6 }}>{res.affected_providers.map((p: string) => <Badge key={p} tone="neutral">{p}</Badge>)}</div></Panel>
            <Panel title="Regression evaluation">{res.evaluation.tests.map((t: any) => <div key={t.test} className="small" style={{ marginBottom: 4 }}><StatusPill status={t.pass ? "PASS" : "FAIL"} /> {t.test}<div className="tiny muted">{t.observed}</div></div>)}</Panel>
            <Panel title="Generated tests">{res.generated_tests.map((t: any) => <div key={t.test_id} className="small"><span className="mono tiny">{t.test_id}</span> — {t.description}</div>)}</Panel>
            <Panel title="Pilot (synthetic replay)"><div className="small">{res.pilot.summary}. Estimated additional review: {res.pilot.additional_review_hours_est} h.</div></Panel>
          </div>
        </div>
      </>)}
    </div>
  );
}
