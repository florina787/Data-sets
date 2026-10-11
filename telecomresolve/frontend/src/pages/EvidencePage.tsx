import { FormEvent, useEffect, useState } from "react";
import { api, enc } from "../api";
import { CitationViewer } from "../components/CitationViewer";
import { EvidencePanel } from "../components/EvidencePanel";
import { Card, Empty, ErrorNote } from "../components/ui";
import { EvidenceResponse } from "../types";

interface KbHit { chunk_id: string; document_id: string; version: string; title: string; heading: string; text: string;
  authority: string; score: number }

export function EvidencePage({ caseId }: { caseId?: string }) {
  const [ev, setEv] = useState<EvidenceResponse | null>(null);
  const [snapshot, setSnapshot] = useState<string | undefined>();
  const [validation, setValidation] = useState<{ checked: number; all_resolve: boolean; failures: unknown[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [openRef, setOpenRef] = useState<string | null>(null);
  const [q, setQ] = useState("dispatch prerequisites");
  const [hits, setHits] = useState<{ mode: string; results: KbHit[] } | null>(null);

  useEffect(() => {
    if (!caseId) return;
    const s = snapshot ? `?snapshot_id=${enc(snapshot)}` : "";
    api<EvidenceResponse>(`/api/cases/${enc(caseId)}/evidence${s}`).then(setEv).catch((e) => setError(e.message));
    api<typeof validation>(`/api/cases/${enc(caseId)}/citations/validate`).then(setValidation).catch(() => setValidation(null));
  }, [caseId, snapshot]);

  const search = (e?: FormEvent) => {
    e?.preventDefault();
    api<{ mode: string; results: KbHit[] }>(`/api/knowledge/search?q=${enc(q)}`).then(setHits).catch((err) => setError(err.message));
  };

  return (
    <div className="grid-2">
      <div className="stack">
        {!caseId ? <Card title="Evidence"><Empty>Open a case in the workspace first.</Empty></Card> : (
          <>
            <Card title={`Evidence for ${caseId}`}>
              <ErrorNote error={error} />
              {ev && ev.snapshots.length > 1 && (
                <label>Evidence snapshot
                  <select value={snapshot ?? ""} onChange={(e) => setSnapshot(e.target.value || undefined)}>
                    <option value="">Latest</option>
                    {ev.snapshots.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
              )}
              {ev?.snapshot && (
                <dl className="kv">
                  <dt>Window</dt><dd>{ev.snapshot.window_start} → {ev.snapshot.window_end}</dd>
                  <dt>Content hash</dt><dd className="mono">{ev.snapshot.content_hash.slice(0, 16)}…</dd>
                  <dt>Derived facts</dt><dd>{ev.snapshot.facts.join(", ")}</dd>
                  <dt>Citation check</dt><dd>{validation ? (validation.all_resolve ? `All ${validation.checked} cited sources resolve`
                    : `${validation.failures.length} citation problem(s)`) : "—"}</dd>
                </dl>
              )}
            </Card>
            <EvidencePanel ev={ev} onOpenRef={setOpenRef} />
          </>
        )}
      </div>
      <Card title="Knowledge search (synthetic documents)">
        <form className="form inline" onSubmit={search}>
          <label className="grow">Query<input value={q} onChange={(e) => setQ(e.target.value)} /></label>
          <button className="btn">Search</button>
        </form>
        {hits && <p className="muted small">Retrieval mode: {hits.mode}. Results are filtered by your tenant and role before scoring.</p>}
        <ul className="evidence-list">
          {hits?.results.map((h) => (
            <li key={h.chunk_id}><strong>{h.title}</strong> — {h.heading} <span className="muted">({h.document_id} v{h.version}, {h.authority})</span>
              <div className="excerpt-inline">{h.text}</div></li>
          ))}
        </ul>
      </Card>
      {openRef && caseId && <CitationViewer caseId={caseId} refId={openRef} snapshotId={snapshot} onClose={() => setOpenRef(null)} />}
    </div>
  );
}
