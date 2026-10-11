import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { Action, Badge, Card, ErrorBox } from "../components";
import { when } from "../format";

export default function Workspace({ onOpen }: { onOpen: (id: string) => void }) {
  const { version, me } = useApp();
  const [changes, setChanges] = useState<any[]>([]);
  const [scen, setScen] = useState<any[]>([]);
  const [err, setErr] = useState<unknown>(null);
  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [metrics, setMetrics] = useState<any>(null);
  const load = () => {
    api("/api/changes").then((d) => setChanges(d.changes)).catch(setErr);
    api("/api/metrics/process").then(setMetrics).catch(() => setMetrics(null));
  };
  useEffect(() => { setErr(null); load(); api("/api/scenarios").then((d) => setScen(d.scenarios)); }, [version]);
  return (
    <div>
      <h1>Change Workspace</h1>
      <p className="muted">Govern beauty-AI changes from requirement to monitored release. Independent prototype; fictional brand, policies and data.</p>
      <ErrorBox error={err} />
      <Card title="Changes">
        <div className="table-wrap">
          <table>
            <thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Candidate</th><th>Updated</th><th></th></tr></thead>
            <tbody>
              {changes.map((c) => (
                <tr key={c.id}>
                  <td><code>{c.id}</code></td><td>{c.title}</td><td><Badge s={c.status} /></td><td><code>{c.candidate_model_id ?? "—"}</code></td>
                  <td className="small">{when(c.updated_at)}</td>
                  <td><button onClick={() => onOpen(c.id)} data-testid={`open-${c.id}`}>Open</button></td>
                </tr>
              ))}
              {changes.length === 0 && <tr><td colSpan={6} className="muted">No changes visible to this persona’s tenant.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>
      {me?.permissions?.includes("change.create") && (
        <Card title="New change request">
          <div className="row"><input aria-label="Title" placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} style={{ flex: 1 }} /></div>
          <textarea aria-label="Change description" placeholder="Describe the change…" value={desc} onChange={(e) => setDesc(e.target.value)} style={{ marginTop: 8 }} />
          <Action label="Create and run requirements agent" primary run={async () => { const c = await api("/api/changes", { method: "POST", body: { title, description: desc } }); onOpen(c.id); }} />
          <p className="small muted">New changes use the same shade-matching fixtures; the requirements agent flags ambiguities from the text.</p>
        </Card>
      )}
      <Card title="Scenario portfolio">
        <table>
          <thead><tr><th>Scenario</th><th>Change</th><th>Status</th><th>Evidence and gates</th></tr></thead>
          <tbody>{scen.map((s) => (
            <tr key={s.id}><td><strong>{s.name}</strong></td><td>{s.change}</td>
              <td><Badge s={s.status.startsWith("IMPLEMENTED") ? "PASS" : "PENDING"} label={s.status} /></td><td className="small">{s.evidence_and_gates}</td></tr>
          ))}</tbody>
        </table>
      </Card>
      {metrics && (
        <Card title="Process metrics (from this prototype's records)">
          <div className="warnbox">{metrics.note}</div>
          <table>
            <thead><tr><th>Metric</th><th>Value</th><th>Definition</th></tr></thead>
            <tbody>{Object.entries(metrics.metrics).map(([k, v]: any) => (
              <tr key={k}><td><code>{k}</code></td><td className="mono">{Array.isArray(v.value) ? (v.value.length ? v.value.join(", ") : "no data") : String(v.value)}</td>
                <td className="small">{v.numerator} / {v.denominator}; window {v.window}; excl. {v.exclusions}; source {v.source}</td></tr>
            ))}</tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
