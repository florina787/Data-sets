import { useEffect, useState } from "react";
import { api, enc } from "../api";
import { useSession } from "../App";
import { Card, Chip, Empty, ErrorNote } from "../components/ui";
import { STATUS_LABEL, fmtTime, human } from "../format";
import { AuditEvent } from "../types";

interface Replay { replayed_status: string; current_status: string; status_matches: boolean; hash_chain_valid: boolean;
  chain_problems: string[]; illegal_transitions: string[]; event_count: number; limits: string;
  steps: { seq: number; at: string; actor: string; node: string | null; from: string | null; to: string; reason: string | null }[];
  recommendations: { recommendation_id: string; action_type: string; snapshot_id: string; snapshot_hash: string; policy_version: string;
    evidence: { ref_id: string; excerpt: string; source_version: string }[] }[] }

export function AuditPage({ caseId }: { caseId?: string }) {
  const { can } = useSession();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [replay, setReplay] = useState<Replay | null>(null);
  const [tenant, setTenant] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (caseId) {
      api<AuditEvent[]>(`/api/cases/${enc(caseId)}/audit`).then(setEvents).catch((e) => setError(e.message));
      api<Replay>(`/api/cases/${enc(caseId)}/audit/replay`).then(setReplay).catch(() => setReplay(null));
    }
    if (can("audit:read")) api<AuditEvent[]>("/api/audit?limit=100").then(setTenant).catch(() => setTenant(null));
  }, [caseId]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="stack">
      <ErrorNote error={error} />
      {caseId && replay && (
        <Card title={`Audit replay — ${caseId}`}>
          <p>
            <Chip tone={replay.hash_chain_valid ? "ok" : "bad"}>{replay.hash_chain_valid ? "Hash chain intact" : "Hash chain broken"}</Chip>{" "}
            <Chip tone={replay.status_matches ? "ok" : "bad"}>Replayed status {STATUS_LABEL[replay.replayed_status] ?? replay.replayed_status}
              {replay.status_matches ? " matches" : " differs from"} current</Chip>{" "}
            <Chip tone={replay.illegal_transitions.length ? "bad" : "ok"}>{replay.illegal_transitions.length} illegal transitions</Chip>
          </p>
          <p className="muted small">{replay.limits}</p>
          <ol className="timeline">
            {replay.steps.map((s) => <li key={s.seq}><time>{fmtTime(s.at)}</time> {s.from ?? "—"} → <strong>{s.to}</strong>
              <span className="muted"> · {s.actor}{s.node ? ` · ${s.node}` : ""}{s.reason ? ` · ${s.reason}` : ""}</span></li>)}
          </ol>
          {replay.recommendations.map((r) => (
            <details key={r.recommendation_id}>
              <summary>Reconstructed recommendation {r.recommendation_id} ({human(r.action_type)}) from snapshot {r.snapshot_id}</summary>
              <ul>{r.evidence.map((e) => <li key={e.ref_id}><strong>{e.ref_id}</strong> ({e.source_version}): {e.excerpt}</li>)}</ul>
            </details>
          ))}
        </Card>
      )}
      {caseId && (
        <Card title={`Case events (${events.length})`}>
          {events.length === 0 ? <Empty>No events.</Empty> : (
            <div className="table-wrap">
              <table>
                <thead><tr><th scope="col">#</th><th scope="col">Time</th><th scope="col">Event</th><th scope="col">Actor</th>
                  <th scope="col">Node</th><th scope="col">Transition</th><th scope="col">Modes</th><th scope="col">Latency</th><th scope="col">Trace</th></tr></thead>
                <tbody>
                  {events.map((e) => (
                    <tr key={e.event_id}>
                      <td>{e.seq}</td><td>{fmtTime(e.occurred_at)}</td><td>{human(e.event_type)}</td>
                      <td>{e.actor_id} <span className="muted small">({e.actor_role})</span></td><td>{e.node ?? "—"}</td>
                      <td>{e.to_status ? `${e.from_status ?? "—"} → ${e.to_status}` : "—"}</td>
                      <td className="small">{e.generation_mode ?? "—"} / {e.connector_mode ?? "—"}</td>
                      <td>{e.latency_ms != null ? `${Math.round(e.latency_ms)} ms` : "—"}</td>
                      <td className="mono small">{e.trace_id.slice(-8)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
      {tenant && (
        <Card title="Tenant audit (latest 100)">
          <ul className="evidence-list">
            {tenant.map((e) => <li key={e.event_id}><time>{fmtTime(e.occurred_at)}</time> <strong>{human(e.event_type)}</strong>
              {" "}{e.case_id ?? ""} <span className="muted">· {e.actor_id}</span>
              {e.event_type === "ACCESS_DENIED" && <span className="muted"> · requested {String(e.detail.requested_case_id)}</span>}</li>)}
          </ul>
        </Card>
      )}
      {!caseId && !tenant && <Card title="Audit"><Empty>Open a case to see its audit trail.</Empty></Card>}
    </div>
  );
}
