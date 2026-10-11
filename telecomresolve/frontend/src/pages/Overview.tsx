import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, Chip, Empty, ErrorNote, StatusChip } from "../components/ui";
import { STATUS_LABEL, fmtTime } from "../format";

interface Dash {
  generated_at: string; case_count: number; by_status: Record<string, number>;
  unresolved: { id: string; title: string; status: string; updated_at: string }[];
  investigation_seconds: { n: number; median: number | null; p95: number | null; definition: string };
  time_to_verified_resolution_minutes: { n: number; median: number | null; definition: string };
  escalations: { case_id: string; reason: string; at: string }[];
  escalation_rate: { numerator: number; denominator: number };
  approval_waits: { approval_id: string; case_id: string; action_type: string; waiting_minutes: number; expired: boolean }[];
  approval_turnaround_minutes: { n: number; median: number | null };
  connector_errors: { case_id: string; event: string; at: string }[];
  stale_evidence: { case_id: string; snapshot_id: string }[];
  recovery_failures: { id: string; outcome: string; reasons: string[] }[];
  executions: { total: number; succeeded: number; unknown: number };
  model_usage: { tokens: number; estimated_cost_usd: number; calls_without_usage_data: number;
    cost_per_investigated_case_usd: number | null; note: string };
  repeat_contacts: { window_days: number; numerator: number; denominator: number; definition: string };
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

const ratio = (n: number, d: number) => (d ? `${n} / ${d}` : "no data");

export function Overview() {
  const [d, setD] = useState<Dash | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Dash>("/api/dashboard").then(setD).catch((e) => setError(e.message)); }, []);
  if (error) return <Card title="Overview"><ErrorNote error={error} /></Card>;
  if (!d) return <Card title="Overview"><p>Loading…</p></Card>;
  const max = Math.max(1, ...Object.values(d.by_status));
  const statuses = Object.entries(d.by_status).sort((a, b) => b[1] - a[1]);
  return (
    <div className="stack">
      <Card title="Operational overview" actions={<span className="muted small">Derived from persisted events · {fmtTime(d.generated_at)}</span>}>
        <div className="tiles">
          <Tile label="Cases in scope" value={String(d.case_count)} sub={`${d.unresolved.length} not resolved`} />
          <Tile label="Investigation time (median)" value={d.investigation_seconds.median != null ? `${d.investigation_seconds.median}s` : "no data"}
                sub={`p95 ${d.investigation_seconds.p95 ?? "—"}s · n=${d.investigation_seconds.n} · wall-clock`} />
          <Tile label="Escalated" value={ratio(d.escalation_rate.numerator, d.escalation_rate.denominator)} sub="investigated cases" />
          <Tile label="Approval turnaround (median)" value={d.approval_turnaround_minutes.median != null ? `${d.approval_turnaround_minutes.median} min` : "no data"}
                sub={`n=${d.approval_turnaround_minutes.n}`} />
          <Tile label="Repeat contacts" value={ratio(d.repeat_contacts.numerator, d.repeat_contacts.denominator)}
                sub={`accounts, ${d.repeat_contacts.window_days}-day window`} />
          <Tile label="Model cost" value={d.model_usage.tokens ? `$${d.model_usage.estimated_cost_usd}` : "$0 (no calls)"}
                sub={d.model_usage.note} />
        </div>
        <p className="muted small">{d.investigation_seconds.definition}. Time to verified resolution: {d.time_to_verified_resolution_minutes.definition}.
          Prototype timings on synthetic data do not demonstrate real-world savings.</p>
      </Card>
      <div className="grid-2">
        <Card title="Cases by status">
          {statuses.length === 0 ? <Empty>No cases.</Empty> : (
            <ul className="bars" aria-label="Number of cases per status">
              {statuses.map(([s, n]) => (
                <li key={s} title={`${STATUS_LABEL[s] ?? s}: ${n} case(s)`}>
                  <span className="bar-label">{STATUS_LABEL[s] ?? s}</span>
                  <span className="bar-track"><span className="bar-fill" style={{ width: `${(n / max) * 100}%` }} /></span>
                  <span className="bar-value">{n}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Waiting on approval">
          {d.approval_waits.length === 0 ? <Empty>No pending approvals.</Empty> : (
            <ul className="evidence-list">{d.approval_waits.map((w) => (
              <li key={w.approval_id}><a href={`#/workspace/${encodeURIComponent(w.case_id)}`}>{w.case_id}</a> · {w.action_type.replace(/_/g, " ")} ·
                waiting {w.waiting_minutes} min {w.expired && <Chip tone="bad">expired</Chip>}</li>))}</ul>
          )}
        </Card>
        <Card title="Unresolved cases">
          {d.unresolved.length === 0 ? <Empty>None.</Empty> : (
            <ul className="evidence-list">{d.unresolved.map((c) => (
              <li key={c.id}><a href={`#/workspace/${encodeURIComponent(c.id)}`}>{c.id}</a> {c.title} <StatusChip status={c.status} /></li>))}</ul>
          )}
        </Card>
        <Card title="Escalations, stale evidence and failures">
          <h4>Escalation reasons</h4>
          {d.escalations.length === 0 ? <Empty>None.</Empty> : <ul>{d.escalations.map((e, i) =>
            <li key={i}><strong>{e.case_id}</strong>: {e.reason}</li>)}</ul>}
          <h4>Stale evidence</h4>
          {d.stale_evidence.length === 0 ? <Empty>None.</Empty> : <ul>{d.stale_evidence.map((s, i) =>
            <li key={i}>{s.case_id} (snapshot {s.snapshot_id})</li>)}</ul>}
          <h4>Recovery not verified or failed</h4>
          {d.recovery_failures.length === 0 ? <Empty>None.</Empty> : <ul>{d.recovery_failures.map((r) =>
            <li key={r.id}><StatusChip status={r.outcome} /> {r.reasons[0]}</li>)}</ul>}
          <h4>Connector errors</h4>
          {d.connector_errors.length === 0 ? <Empty>None recorded.</Empty> : <ul>{d.connector_errors.map((c, i) =>
            <li key={i}>{c.case_id}: {c.event}</li>)}</ul>}
          <p className="muted small">Executions: {d.executions.succeeded} succeeded, {d.executions.unknown} outcome unknown, {d.executions.total} total (simulated).</p>
        </Card>
      </div>
    </div>
  );
}
