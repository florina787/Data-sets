"use client";

import { useState } from "react";
import { Badge, Empty, ErrorBox, PageHead, Panel, Spinner } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";

export default function KnowledgePage() {
  const { userId, matterId } = useAppState();
  const docs = useApi<any[]>(`/knowledge/documents?matter_id=${matterId}`, userId);
  const [q, setQ] = useState("change of control veto escalation");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const search = async () => {
    setBusy(true); setErr(null);
    try { setRes(await api.post("/knowledge/search", userId, { matter_id: matterId, query: q, top_k: 8 })); } catch (e) { setErr(e as ApiError); setRes(null); } finally { setBusy(false); }
  };
  return (
    <div className="page">
      <PageHead title="Knowledge" description="Permission-aware retrieval. Security filters (user, client, matter, role, ethical wall, document permission) are applied BEFORE retrieval - unauthorised partitions are never read or scored." />
      <Panel title="Search the permitted corpus">
        <form className="row" onSubmit={(e) => { e.preventDefault(); search(); }}>
          <input className="input" style={{ flex: 1, minWidth: 240 }} value={q} onChange={(e) => setQ(e.target.value)} aria-label="Query" />
          <button className="btn btn-primary" disabled={busy}>Search</button>{busy && <Spinner />}
        </form>
        <ErrorBox error={err} />
        {res && (<div className="stack" style={{ marginTop: 12 }}>
          <div className="notice">Scope: matter <span className="mono">{res.scope.matter_id}</span> · partitions {res.scope.partitions.map((p: string) => <Badge key={p} tone="neutral">{p}</Badge>)} · clearance {res.scope.max_sensitivity}</div>
          {res.results.length === 0 ? <Empty title="No results in your permitted scope" /> : res.results.map((r: any) => (
            <div key={r.source_id} className="panel" style={{ padding: 10 }}>
              <div className="row" style={{ justifyContent: "space-between" }}><span className="strong small">{r.title}</span>
                <span className="row"><Badge tone="info">{humanize(r.kind)}</Badge><Badge tone="neutral">{r.access_label}</Badge>{r.untrusted_instruction_detected && <Badge tone="bad">untrusted instruction</Badge>}</span></div>
              <div className="tiny mono muted">{r.doc_id} §{r.section_id} · score {r.score.toFixed(2)}</div>
              <div className="small">{r.text}</div></div>))}
        </div>)}
      </Panel>
      <div style={{ marginTop: 12 }}><Panel title="Knowledge documents visible to you" bodyClass="table-wrap">
        <ErrorBox error={docs.error} />
        <table className="table"><thead><tr><th>Document</th><th>Kind</th><th>Access label</th><th>Sensitivity</th></tr></thead>
          <tbody>{(docs.data ?? []).map((d) => <tr key={d.doc_id}><td><div className="small strong">{d.title}</div><div className="tiny mono muted">{d.doc_id}</div></td>
            <td>{humanize(d.kind)}</td><td className="mono tiny">{d.access_label}</td><td>{humanize(d.sensitivity)}</td></tr>)}</tbody></table>
      </Panel></div>
    </div>
  );
}
