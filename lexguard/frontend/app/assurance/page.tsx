"use client";

import { useState } from "react";
import { Badge, Bar, Empty, ErrorBox, Kpi, LoadingBlock, PageHead, Panel, Spinner, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize, pct } from "@/lib/format";

function Pipeline({ stages }: { stages: { stage: string; status: string; detail: string }[] }) {
  return (
    <div className="pipeline">
      {stages.map((s, i) => (
        <div className="pipe-step" key={s.stage}>
          <span className="pipe-dot" aria-hidden="true">{i + 1}</span>
          <div><div className="row"><span className="strong small">{s.stage}</span><StatusPill status={s.status === "COMPLETE" ? "ok" : s.status} label={humanize(s.status)} /></div>
            <div className="tiny muted">{s.detail}</div></div>
        </div>))}
    </div>
  );
}

export default function AssurancePage() {
  const { userId, matterId } = useAppState();
  const wps = useApi<any[]>(`/review/work-products?matter_id=${matterId}`, userId);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<any>(null);
  const run = async (destination: string) => {
    setBusy(true); setErr(null);
    try { setResult(await api.post("/assurance/evaluate", userId, { matter_id: "M-1001", work_product_id: "WP-MEMO-MAPLE-001", destination })); }
    catch (e) { setErr(e as ApiError); } finally { setBusy(false); }
  };
  const open = async (id: string) => { try { setSelected(await api.get(`/review/work-products/${id}`, userId)); } catch (e) { setErr(e as ApiError); } };
  const a = result?.assurance;
  return (
    <div className="page">
      <PageHead title="WorkProduct Assurance" description="Proposition extraction → source mapping → citation verification → groundedness → playbook → matter policy → confidentiality → assurance → human review.">
        <button className="btn btn-primary" onClick={() => run("external_client")} disabled={busy}>Verify AI memo (Project Maple, external)</button>
        {busy && <Spinner />}
      </PageHead>
      <ErrorBox error={err} />
      {a && (
        <div className="grid grid-2" style={{ marginBottom: 12 }}>
          <Panel title="Assurance result">
            <div className="grid grid-3" style={{ marginBottom: 10 }}>
              <Kpi label="Assurance score" value={`${a.score_pct}%`} tone={a.status === "PASS" ? "good" : "warn"} tip="Traceability and verification completeness - NOT legal correctness." />
              <Kpi label="Status" value={<StatusPill status={a.status} />} />
              <Kpi label="External delivery" value={a.external_delivery_allowed ? "Allowed" : "Blocked"} tone={a.external_delivery_allowed ? "good" : "bad"} />
            </div>
            <div className="notice" style={{ marginBottom: 10 }}>{a.meaning}</div>
            {Object.entries(a.components).map(([k, v]: any) => (
              <div key={k} style={{ marginBottom: 6 }}><div className="row tiny" style={{ justifyContent: "space-between" }}><span>{humanize(k)} (weight {a.weights[k]})</span><span className="mono">{pct(v)}</span></div>
                <Bar value={v} tone={v >= 0.95 ? "good" : v >= 0.8 ? "warn" : "bad"} /></div>))}
            <div className="tiny muted">Unsupported-claim penalty: 0.5 × {pct(a.unsupported_claim_rate, 1)}</div>
            {a.blocking_issues.map((b: string) => <div key={b} className="small" style={{ marginTop: 4 }}><Badge tone="warn">issue</Badge> {b}</div>)}
          </Panel>
          <Panel title="Pipeline"><Pipeline stages={a.stages} /></Panel>
        </div>)}
      {result && (
        <Panel title="Citation verification - 10 propositions" bodyClass="table-wrap">
          <table className="table"><thead><tr><th>#</th><th>Claim</th><th>Citation</th><th>Status</th><th>Evidence</th></tr></thead>
            <tbody>{result.verifications.map((v: any) => (
              <tr key={v.pid}><td className="mono">{v.pid}</td><td className="small">{v.claim}</td><td className="mono tiny">{v.doc_id} §{v.section_id}</td>
                <td><StatusPill status={v.status} /><div className="tiny muted">{v.reasons.join(" ")}</div></td>
                <td className="tiny" style={{ maxWidth: 320 }}>{v.evidence_text}</td></tr>))}</tbody></table>
        </Panel>)}
      <div className="grid grid-2" style={{ marginTop: 12 }}>
        <Panel title="Work products on the active matter" bodyClass="table-wrap">
          {wps.loading && !wps.data ? <LoadingBlock /> : !wps.data?.length ? <Empty title="No work products yet">Run a Copilot review to create one.</Empty> : (
            <table className="table"><thead><tr><th>Work product</th><th>Assurance</th><th>Status</th></tr></thead>
              <tbody>{wps.data.map((w) => (
                <tr key={w.work_product_id} className="clickable" onClick={() => open(w.work_product_id)}>
                  <td><div className="small strong">{w.title}</div><div className="tiny mono muted">{w.work_product_id}</div></td>
                  <td>{w.assurance_pct != null ? `${w.assurance_pct}%` : "-"} <StatusPill status={w.assurance_status} /></td><td><StatusPill status={w.status} /></td></tr>))}</tbody></table>)}
        </Panel>
        <Panel title="Work product detail">
          {!selected ? <Empty title="Select a work product" /> : (
            <div className="stack">
              <div className="row"><StatusPill status={selected.status} /><span className="mono tiny">{selected.work_product_id}</span></div>
              <div className="small">{selected.title}</div>
              {selected.assurance?.stages && <Pipeline stages={selected.assurance.stages} />}
              {selected.reviews.map((r: any, i: number) => <div key={i} className="small"><Badge tone="info">{r.decision}</Badge> by {r.reviewer_id} for {humanize(r.destination)} — {r.comment}</div>)}
            </div>)}
        </Panel>
      </div>
    </div>
  );
}
