import { useState } from "react";
import { api } from "../api";
import { Card, Empty, Notice, Provenance, Short, Status, Time } from "../components/ui";
import { useApp } from "../context";
import { usePoll } from "../hooks";

export default function Evidence() {
  const { runId } = useApp();
  const ev = usePoll<any>(runId ? `/api/evidence?run_id=${runId}` : "/api/evidence", 5000);
  const audit = usePoll<any>("/api/audit", 5000);
  const [q, setQ] = useState("once per customer limit scope");
  const [hits, setHits] = useState<any[] | null>(null);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Evidence and audit</h1>
      <Notice kind="info">Evidence and audit rows are only ever appended through the application APIs. SQLite is not tamper-proof, and no cryptographic integrity is claimed.</Notice>
      <Card title="Source documents (local retrieval index)">
        <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); api(`/api/documents/search?q=${encodeURIComponent(q)}`).then((d) => setHits(d.results)); }}>
          <label htmlFor="q" className="sr-only">Search documents</label>
          <input id="q" className="w-80 rounded border border-cream-300 px-2 py-1 text-sm" value={q} onChange={(e) => setQ(e.target.value)} />
          <button className="btn-ghost">Search</button>
        </form>
        {hits && (hits.length === 0 ? <div className="mt-2"><Empty>No section matches. Treat this as an evidence gap.</Empty></div> : (
          <ul className="mt-2 space-y-1 text-sm">{hits.map((h) => <li key={h.ref} className="rounded bg-cream-50 p-2"><b>{h.ref}</b> {h.heading} <span className="text-xs text-navy-600">(score {h.score}, effective {h.effective})</span><div className="text-xs">{h.excerpt}</div></li>)}</ul>
        ))}
      </Card>
      <Card title={`Evidence registry${runId ? ` · ${runId}` : ""}`}>
        {!ev.data?.evidence?.length ? <Empty>No evidence yet.</Empty> : (
          <div className="max-h-[480px] overflow-auto">
            <table className="table">
              <thead><tr><th>ID</th><th>Time</th><th>Type</th><th>Provenance</th><th>Source</th><th>Revision</th><th>Summary</th></tr></thead>
              <tbody>{ev.data.evidence.map((e: any) => (
                <tr key={e.id}><td className="font-mono text-xs">{e.id}</td><td className="text-xs"><Time value={e.ts} /></td><td className="text-xs">{e.type}</td><td><Provenance kind={e.provenance} /></td><td className="text-xs">{e.source}</td><td><Short value={e.revision} /></td><td className="text-xs">{e.summary}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
      <Card title="Audit log (including rejected actions)">
        {!audit.data?.events?.length ? <Empty>No events.</Empty> : (
          <div className="max-h-[480px] overflow-auto">
            <table className="table">
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Outcome</th><th>Entity</th><th>Detail</th></tr></thead>
              <tbody>{audit.data.events.map((e: any) => (
                <tr key={e.id}><td className="text-xs"><Time value={e.ts} /></td><td className="text-xs">{e.actor}</td><td className="font-mono text-xs">{e.action}</td><td><Status value={e.outcome} /></td><td className="font-mono text-xs">{e.entity_type ? `${e.entity_type}:${e.entity_id ?? ""}` : "-"}</td><td className="max-w-md truncate text-xs" title={e.detail_json}>{e.detail_json}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
