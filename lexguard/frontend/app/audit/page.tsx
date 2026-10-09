"use client";

import { useState } from "react";
import { Badge, Empty, ErrorBox, LoadingBlock, PageHead, Panel } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { api, ApiError } from "@/lib/api";
import { humanize } from "@/lib/format";
import type { AuditEvent, MatterSummary } from "@/types/api";

function Events({ events, onRequest }: { events: AuditEvent[]; onRequest?: (id: string) => void }) {
  if (!events.length) return <Empty title="No audit events yet">Use the Copilot on this matter to generate an audit trail.</Empty>;
  return (
    <table className="table"><thead><tr><th>Time</th><th>Event</th><th>Severity</th><th>User</th><th>Request</th><th>Details</th></tr></thead>
      <tbody>{events.map((e) => <tr key={e.event_id}><td className="tiny mono">{e.ts?.replace("T", " ").slice(0, 19)}</td>
        <td className="small strong">{humanize(e.event_type)}</td>
        <td><Badge tone={e.severity === "CRITICAL" ? "bad" : e.severity === "WARNING" ? "warn" : "neutral"}>{e.severity}</Badge></td>
        <td className="mono tiny">{e.user_id}</td>
        <td className="mono tiny">{e.request_id ? <button className="btn btn-ghost btn-sm mono" onClick={() => onRequest?.(e.request_id!)}>{e.request_id.slice(0, 12)}…</button> : "—"}</td>
        <td className="tiny mono" style={{ maxWidth: 420, wordBreak: "break-all" }}>{JSON.stringify(e.payload).slice(0, 200)}</td></tr>)}</tbody></table>
  );
}

export default function AuditPage() {
  const { userId, matterId, setMatterId } = useAppState();
  const matters = useApi<MatterSummary[]>("/matters", userId);
  const log = useApi<any>(`/audit/${matterId}`, userId);
  const [trace, setTrace] = useState<{ request_id: string; chain: AuditEvent[] } | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const openTrace = async (rid: string) => { setErr(null); try { setTrace(await api.trace(userId, rid)); } catch (e) { setErr(e as ApiError); } };
  return (
    <div className="page">
      <PageHead title="Audit" description="Tamper-evident (hash-chained) audit: User → Client → Matter → Task → Policy → Access → Routing → Provider → Sources → Agents → Work product → Assurance → Human review → Final status.">
        <select className="select" value={matterId} onChange={(e) => setMatterId(e.target.value)} aria-label="Matter">
          {(matters.data ?? []).map((m) => <option key={m.matter_id} value={m.matter_id}>{m.name}</option>)}</select>
        <button className="btn" onClick={log.reload}>Refresh</button>
      </PageHead>
      <ErrorBox error={log.error} />
      <ErrorBox error={err} />
      {log.data && <div className="row" style={{ marginBottom: 10 }}>
        <Badge tone={log.data.chain_integrity.valid ? "good" : "bad"}>Chain integrity: {log.data.chain_integrity.valid ? "VALID" : "BROKEN"}</Badge>
        <span className="tiny muted">{log.data.chain_integrity.events} events in ledger</span></div>}
      {trace && (
        <div style={{ marginBottom: 12 }}><Panel title={<>Reverse trace · <span className="mono small">{trace.request_id}</span></>} actions={<button className="btn btn-sm" onClick={() => setTrace(null)}>Close</button>} bodyClass="table-wrap">
          <div className="row" style={{ padding: "8px 14px", gap: 4 }}>{trace.chain.map((e, i) => <span key={e.event_id} className="row" style={{ gap: 4 }}>
            <Badge tone="info">{humanize(e.event_type)}</Badge>{i < trace.chain.length - 1 && <span className="muted">→</span>}</span>)}</div>
          <Events events={trace.chain} />
        </Panel></div>)}
      <Panel title="Matter audit log" bodyClass="table-wrap">
        {log.loading && !log.data ? <LoadingBlock /> : log.data ? <Events events={log.data.events} onRequest={openTrace} /> : null}
      </Panel>
    </div>
  );
}
