import { STATUS_LABEL, fmtTime, human } from "../format";
import { AuditEvent } from "../types";
import { Card, Empty } from "./ui";

const NODES = ["triage", "evidence", "diagnosis", "planning", "human_review"];

export function WorkflowStatus({ events, running }: { events: AuditEvent[]; running: boolean }) {
  const lastStart = [...events].reverse().find((e) => e.event_type === "INVESTIGATION_STARTED");
  const since = lastStart ? events.filter((e) => e.seq >= lastStart.seq) : [];
  const done = new Set(since.map((e) => e.node).filter(Boolean) as string[]);
  return (
    <ol className="nodes" aria-label="Workflow nodes">
      {NODES.map((n) => {
        const state = done.has(n) ? "done" : running ? "pending" : "idle";
        return (
          <li key={n} className={`node node-${state}`}>
            <span aria-hidden="true">{state === "done" ? "✓" : "○"}</span> {human(n)}
            <span className="sr-only">{state === "done" ? " completed" : " not run"}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function Timeline({ events }: { events: AuditEvent[] }) {
  if (!events.length) return <Card title="Timeline"><Empty>No events yet.</Empty></Card>;
  return (
    <Card title="Timeline" actions={<span className="muted small">From persisted audit events</span>}>
      <ol className="timeline">
        {events.map((e) => (
          <li key={e.event_id}>
            <time dateTime={e.occurred_at}>{fmtTime(e.occurred_at)}</time>{" "}
            <strong>{e.to_status ? `${STATUS_LABEL[e.from_status ?? ""] ?? e.from_status ?? "—"} → ${STATUS_LABEL[e.to_status] ?? e.to_status}` : human(e.event_type)}</strong>
            {e.node && <span className="muted"> · {e.node}</span>}
            <span className="muted"> · {e.actor_id}</span>
            {typeof e.detail.reason === "string" && <div className="small muted">{e.detail.reason}</div>}
            {typeof e.detail.summary === "string" && <div className="small">{e.detail.summary}</div>}
          </li>
        ))}
      </ol>
    </Card>
  );
}
