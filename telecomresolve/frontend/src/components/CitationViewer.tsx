import { useEffect, useState } from "react";
import { api, enc } from "../api";
import { EvidenceItem } from "../types";
import { Chip, ErrorNote, Modal } from "./ui";

interface Resolved {
  item: EvidenceItem; snapshot_id: string; resolves: boolean; problem: string | null;
  record: Record<string, unknown> & { samples?: Record<string, unknown>[]; text?: string; warning?: string };
}

const SAMPLE_COLS = ["collected_at", "link_state", "loss_of_signal_events", "link_retrains", "snr_margin_db",
  "crc_errors", "packet_loss_pct", "cpe_unexpected_reboots", "simulated_post_action"];

export function CitationViewer({ caseId, refId, snapshotId, onClose }:
  { caseId: string; refId: string; snapshotId?: string; onClose: () => void }) {
  const [data, setData] = useState<Resolved | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const q = snapshotId ? `?snapshot_id=${enc(snapshotId)}` : "";
    api<Resolved>(`/api/cases/${enc(caseId)}/evidence/${enc(refId)}${q}`).then(setData)
      .catch((e) => setError(e.message));
  }, [caseId, refId, snapshotId]);
  return (
    <Modal title={`Source ${refId}`} onClose={onClose}>
      <ErrorNote error={error} />
      {!data && !error && <p>Loading source…</p>}
      {data && (
        <div className="stack">
          <dl className="kv">
            <dt>Source</dt><dd>{data.item.source_type} · {data.item.source_id}</dd>
            <dt>Version / time</dt><dd>{data.item.source_version}</dd>
            <dt>Authority</dt><dd>{data.item.authority} ({data.item.kind})</dd>
            <dt>Freshness</dt><dd>{data.item.freshness}</dd>
            <dt>Retrieved</dt><dd>{data.item.retrieved_at}</dd>
            <dt>Resolves</dt>
            <dd>{data.resolves ? <Chip tone="ok">Verified against source</Chip>
              : <Chip tone="bad">Does not resolve: {data.problem}</Chip>}</dd>
          </dl>
          {data.record.warning && <p className="warn-note" role="note"><strong>Warning:</strong> {data.record.warning}</p>}
          <blockquote className="excerpt">{data.item.excerpt}</blockquote>
          {data.item.supports.length > 0 && <p>Supports (by rule): {data.item.supports.join(", ")}</p>}
          {data.item.opposes.length > 0 && <p>Opposes (by rule): {data.item.opposes.join(", ")}</p>}
          {data.record.text && (
            <details open><summary>Full document section</summary><p className="doc-text">{String(data.record.text)}</p></details>
          )}
          {data.record.samples && (
            <div className="table-wrap" tabIndex={0} aria-label="Diagnostic samples">
              <table>
                <caption>{data.record.samples.length} measured samples cited</caption>
                <thead><tr>{SAMPLE_COLS.map((c) => <th key={c} scope="col">{c.replace(/_/g, " ")}</th>)}</tr></thead>
                <tbody>
                  {data.record.samples.map((s) => (
                    <tr key={String(s.id)}>{SAMPLE_COLS.map((c) => <td key={c}>{String(s[c] ?? "—")}</td>)}</tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {!data.record.samples && !data.record.text && (
            <pre className="record">{JSON.stringify(data.record, null, 2)}</pre>
          )}
        </div>
      )}
    </Modal>
  );
}

export function RefLink({ refId, onOpen }: { refId: string; onOpen: (ref: string) => void }) {
  return <button className="ref-link" onClick={() => onOpen(refId)} aria-label={`Open source ${refId}`}>[{refId}]</button>;
}
