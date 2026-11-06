import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, Chip, Empty, ErrorNote, StatusChip } from "../components/ui";
import { ACTION_LABEL, fmtTime } from "../format";
import { Approval } from "../types";

export function Approvals() {
  const [rows, setRows] = useState<Approval[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Approval[]>("/api/approvals").then(setRows).catch((e) => setError(e.message)); }, []);
  return (
    <Card title="Approvals">
      <ErrorNote error={error} />
      <p className="muted">Decisions are made inside the case so the reviewer sees the evidence and the bound payload.</p>
      {rows === null ? <p>Loading…</p> : rows.length === 0 ? <Empty>No approval records in your scope.</Empty> : (
        <div className="table-wrap">
          <table>
            <thead><tr><th scope="col">Case</th><th scope="col">Action</th><th scope="col">Status</th><th scope="col">Requested</th>
              <th scope="col">Required role</th><th scope="col">Waiting</th><th scope="col">You can decide</th></tr></thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td><a href={`#/workspace/${encodeURIComponent(a.case_id)}`}>{a.case_id}</a><div className="small muted">{a.case_title}</div>
                    {a.case_status && <StatusChip status={a.case_status} />}</td>
                  <td>{ACTION_LABEL[a.action_type] ?? a.action_type}</td>
                  <td><Chip tone={a.status === "pending" ? "warn" : a.status === "rejected" ? "bad" : a.status === "consumed" || a.status === "approved" ? "ok" : "neutral"}>
                    {a.status === "pending" ? "Pending approval" : a.status}</Chip>{a.expired && a.status === "pending" && <Chip tone="bad">expired</Chip>}</td>
                  <td>{fmtTime(a.requested_at)} by {a.requested_by}</td>
                  <td>{a.required_roles.join(", ")}{a.separation_of_duties && " (not proposer)"}</td>
                  <td>{a.wait_minutes} min</td>
                  <td>{a.can_decide ? <Chip tone="ok">Yes</Chip> : <Chip tone="neutral">No</Chip>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
