"use client";

import { useState } from "react";
import { Badge, ErrorBox, LoadingBlock, PageHead, Panel, Spinner, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";

const fmt = (m: string, v: number) => (m === "latency_ms" ? `${v} ms` : m === "estimated_cost_usd" ? `$${v}` : `${(v * 100).toFixed(1)}%`);

export default function EvaluationPage() {
  const { userId } = useAppState();
  const versions = useApi<any[]>("/evaluation/versions", userId);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [promo, setPromo] = useState<any>(null);
  const run = async (target: string) => {
    setBusy(target); setErr(null); setPromo(null);
    try { setRes(await api.post("/evaluation/run", userId, { target })); versions.reload(); } catch (e) { setErr(e as ApiError); } finally { setBusy(null); }
  };
  const promote = async () => {
    setErr(null);
    try { setPromo(await api.post("/evaluation/promote", userId, { target: res.target, run_id: res.run_id })); versions.reload(); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="page">
      <PageHead title="AI Evaluation Lab" description="Baseline vs candidate regression evaluation over golden sets. Safety gates (policy, isolation, refusal, confidentiality) must be 100%. Promotion requires AI Governance approval." />
      <ErrorBox error={err} />
      {err?.status === 403 && <div className="notice" style={{ marginTop: 8 }}>Switch the signed-in user to <strong>Tom Becker — AI Governance</strong> to run evaluations and promote versions.</div>}
      <Panel title="Versioned components" bodyClass="table-wrap">
        {versions.loading && !versions.data ? <LoadingBlock /> : (
          <table className="table"><thead><tr><th>Component</th><th>Kind</th><th>Production</th><th>Candidate</th><th>Last evaluation</th><th /></tr></thead>
            <tbody>{(versions.data ?? []).map((v) => <tr key={v.target}><td><div className="strong small">{v.target}</div><div className="tiny muted">{v.description}</div></td>
              <td>{humanize(v.kind)}</td><td className="mono">v{v.production}</td><td className="mono">{v.candidate ? `v${v.candidate}` : "—"}</td>
              <td>{v.last_evaluation ? <StatusPill status={v.last_evaluation.gates_passed ? "PASS" : "FAIL"} label={v.last_evaluation.gates_passed ? "Gates passed" : "Gates failed"} /> : <span className="muted small">never</span>}</td>
              <td><button className="btn btn-sm" disabled={!!busy || !v.candidate} onClick={() => run(v.target)}>{busy === v.target ? "Running…" : "Run evaluation"}</button></td></tr>)}</tbody></table>)}
      </Panel>
      {busy && <div style={{ marginTop: 8 }}><Spinner label="Running golden sets through the real pipeline (baseline and candidate)" /></div>}
      {res && (
        <div style={{ marginTop: 12 }}>
          <Panel title={<>{res.target}: v{res.baseline_version} → v{res.candidate_version}</>} actions={
            <div className="row"><StatusPill status={res.gates_passed ? "PASS" : "FAIL"} label={res.recommendation} />
              {res.gates_passed && !promo && <button className="btn btn-primary btn-sm" onClick={promote}>Approve &amp; promote</button>}</div>} bodyClass="table-wrap">
            <div className="tiny muted" style={{ padding: "8px 14px" }}>Baseline config <span className="mono">{JSON.stringify(res.baseline_config)}</span> · Candidate config <span className="mono">{JSON.stringify(res.candidate_config)}</span> · {res.demo_mode_note}</div>
            <table className="table"><thead><tr><th>Metric</th><th className="right">Baseline</th><th className="right">Candidate</th><th className="right">Δ</th><th>Gate</th><th>Result</th></tr></thead>
              <tbody>{res.metrics.map((m: any) => <tr key={m.metric}><td><div className="small strong">{humanize(m.metric)}</div><div className="tiny muted">{m.description}</div></td>
                <td className="right mono">{fmt(m.metric, m.baseline)}</td><td className="right mono">{fmt(m.metric, m.candidate)}</td>
                <td className="right mono">{m.delta === 0 ? "—" : <Badge tone={m.improved ? "good" : "warn"}>{m.delta > 0 ? "+" : ""}{m.metric.endsWith("ms") || m.metric.endsWith("usd") ? m.delta : (m.delta * 100).toFixed(1)}</Badge>}</td>
                <td className="tiny">{m.gate}</td><td><StatusPill status={m.pass ? "PASS" : "FAIL"} /></td></tr>)}</tbody></table>
          </Panel>
          {promo && <div className="status-banner tone-good" style={{ marginTop: 8 }}>Promoted {promo.target} to v{promo.promoted_version} ({promo.deployment} deployment) by {promo.approved_by}.</div>}
        </div>)}
    </div>
  );
}
