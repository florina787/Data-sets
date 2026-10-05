"use client";

import { useState } from "react";
import { Badge, ErrorBox, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";

export default function PlaybooksPage() {
  const { userId } = useAppState();
  const { data, error, loading } = useApi<any[]>("/playbooks", userId);
  const [text, setText] = useState("Accept unrestricted counterparty veto over the Change of Control in the supply agreement.");
  const [kind, setKind] = useState("recommendation");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const check = async () => {
    setErr(null);
    try { setRes(await api.post("/playbook/check", userId, { playbook_id: "PB-MA-COC", items: [{ id: "TEST", text, kind }] })); } catch (e) { setErr(e as ApiError); }
  };
  return (
    <div className="page">
      <PageHead title="Playbooks · PlaybookGuard" description="Synthetic practice playbooks. Clauses and AI recommendations are compared deterministically: ALIGNED, DEVIATION or ESCALATION REQUIRED." />
      <Panel title="Check a clause or AI recommendation against the M&A playbook">
        <div className="stack">
          <select className="select" value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Item type" style={{ width: 220 }}>
            <option value="recommendation">AI recommendation</option><option value="clause">Contract clause</option></select>
          <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} aria-label="Text to check" />
          <div><button className="btn btn-primary" onClick={check}>Check against playbook</button></div>
          <ErrorBox error={err} />
          {res && res.results.map((r: any) => (
            <div key={r.subject_id} className="row"><StatusPill status={r.result} /><span className="small">{r.explanation}</span>
              {r.rule_id && <Badge tone="neutral">{r.rule_id}</Badge>}</div>))}
        </div>
      </Panel>
      <ErrorBox error={error} />
      {loading && !data ? <LoadingBlock /> : (data ?? []).map((p) => (
        <div key={p.playbook_id} style={{ marginTop: 12 }}>
          <Panel title={<>{p.title} <span className="muted small">v{p.version} · {p.practice}</span></>} bodyClass="table-wrap">
            <table className="table"><thead><tr><th>Rule</th><th>Topic</th><th>Outcome</th><th>Standard position</th></tr></thead>
              <tbody>{p.rules.map((r: any) => <tr key={r.rule_id}><td className="mono small">{r.rule_id}</td><td>{r.topic}</td>
                <td><StatusPill status={r.result} /></td><td className="small">{r.standard_position}</td></tr>)}</tbody></table>
          </Panel>
        </div>))}
    </div>
  );
}
