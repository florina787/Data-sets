import { useState } from "react";
import { post } from "../api";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "–" : `${(v * 100).toFixed(1)}%`);
const num = (v: number | null | undefined, d = 3) => (v === null || v === undefined ? "–" : v.toFixed(d));

function Badge({ tone, children }: { tone: "ok" | "warn" | "muted" | "bad"; children: string }) {
  const cls = { ok: "bg-leaf-100 text-leaf-700", warn: "bg-amber-100 text-amber-700", muted: "bg-surface-raised text-navy-700", bad: "bg-brick-100 text-brick-700" }[tone];
  return <span className={`whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-semibold ${cls}`}>{children}</span>;
}

function Confusion({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  const max = Math.max(1, ...matrix.flat());
  return (
    <table className="text-xs" aria-label="Confusion matrix: rows are true grades, columns are predicted grades">
      <thead><tr><th className="p-1 text-left text-navy-600">true ↓ / predicted →</th>{labels.map((l) => <th key={l} className="p-1 text-navy-600">{l}</th>)}</tr></thead>
      <tbody>{matrix.map((row, i) => (
        <tr key={labels[i]}><th className="p-1 text-left text-navy-700">{labels[i]}</th>
          {row.map((v, j) => (
            <td key={j} className="p-1 text-center font-mono" style={{ background: v ? `rgba(${i === j ? "16,185,129" : "239,68,68"},${0.15 + 0.6 * (v / max)})` : "transparent" }}>{v}</td>
          ))}
        </tr>
      ))}</tbody>
    </table>
  );
}

export default function EvaluationLab() {
  const { data, error, refresh } = usePoll<any>("/api/ml/registry", 15000);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const run = async () => {
    setBusy(true); setMessage(null);
    try { const r = await post("/api/ml/evaluations/synthetic"); setMessage(`Evaluated ${r.images} synthetic images in ${(r.duration_ms / 1000).toFixed(1)} s.`); refresh?.(); }
    catch (e) { setMessage((e as Error).message); } finally { setBusy(false); }
  };
  const evals: any[] = data?.evaluations ?? [];
  const latestGrading = evals.find((e) => e.task === "grading");
  const trained = (data?.models ?? []).filter((m: any) => m.trained).length;
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Model Evaluation Lab</h1>
          <p className="text-sm text-navy-600">Every result names the model version, dataset version, split, sample size, date and method, so models are compared like for like.</p>
        </div>
        <button className="btn-primary" onClick={run} disabled={busy}>{busy ? "Evaluating…" : "Run evaluation on the synthetic set"}</button>
      </div>
      <Notice kind="warn">
        <strong>{trained === 0 ? "No trained model is registered yet." : `${trained} trained model(s) registered.`}</strong>{" "}
        The current detector and grader are rule-based. Results on the synthetic set (drawn shapes) check the pipeline only and say nothing about accuracy on real potatoes. Import labelled photos with <code className="font-mono">scripts/eval_vision.py --dataset</code> to measure that.
      </Notice>
      {message && <Notice>{message}</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? <Empty>Loading…</Empty> : (
        <>
          <Card title="Evaluation reports">
            {evals.length === 0 ? <Empty>No evaluations yet. Run one above.</Empty> : (
              <div className="overflow-x-auto">
                <table className="table">
                  <thead><tr><th>Date</th><th>Model</th><th>Dataset</th><th>Split · n</th><th>Task</th><th>Key results</th></tr></thead>
                  <tbody>{evals.map((e) => {
                    const m = e.metrics;
                    return (
                      <tr key={e.id}>
                        <td className="whitespace-nowrap text-xs">{new Date(e.created_at).toLocaleString()}</td>
                        <td className="font-mono text-xs">{e.model_id} {!e.model_trained && <Badge tone="muted">not trained</Badge>}</td>
                        <td className="text-xs">{e.dataset_id} {e.dataset_synthetic && <Badge tone="warn">SYNTHETIC</Badge>}</td>
                        <td className="text-xs">{e.split} · {e.sample_size}</td>
                        <td className="text-xs">{e.task}</td>
                        <td className="text-xs">{e.task === "grading"
                          ? <>accuracy {pct(m.accuracy)} · macro F1 {num(m.macro_f1)}</>
                          : <>mAP@50 {num(m.map50)} · mAP@50:95 {num(m.map50_95)} · P {pct(m.per_class?.all?.precision50)} · R {pct(m.per_class?.all?.recall50)} · count MAE {num(m.counting?.mae, 2)} · exact count {pct(m.counting?.exact_count_accuracy)} · {m.inference_ms_per_image} ms/image</>}
                          <div className="text-[11px] text-navy-600">{e.method}</div></td>
                      </tr>
                    );
                  })}</tbody>
                </table>
              </div>
            )}
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Latest grading confusion matrix">
              {latestGrading ? <><Confusion labels={latestGrading.metrics.labels} matrix={latestGrading.metrics.confusion_matrix} />
                <p className="mt-2 text-xs text-navy-600">{latestGrading.model_id} on {latestGrading.dataset_id}{latestGrading.dataset_synthetic ? " (SYNTHETIC)" : ""}, {latestGrading.sample_size} matched potatoes.</p></>
                : <Empty>No grading evaluation yet.</Empty>}
            </Card>
            <Card title="Datasets">
              <ul className="space-y-2 text-sm">{data.datasets.map((d: any) => (
                <li key={d.id} className="rounded-lg border border-surface-line p-2">
                  <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs">{d.id}</span>{d.synthetic ? <Badge tone="warn">SYNTHETIC</Badge> : <Badge tone="ok">real images</Badge>}</div>
                  <div className="text-xs text-navy-600">{d.n_images} images · {d.n_objects} labelled objects · splits {JSON.stringify(d.splits)}</div>
                  <div className="text-xs text-navy-600">Licence: {d.license} · Source: {d.source}</div>
                  {d.governance?.method && <div className="text-xs text-navy-600">Leakage check: {d.governance.near_duplicate_merges} near-duplicate merges, {d.governance.cross_split_near_duplicates} cross-split duplicates</div>}
                </li>
              ))}{data.datasets.length === 0 && <Empty>No datasets registered yet.</Empty>}</ul>
            </Card>
          </div>
          <Card title="Model registry">
            <table className="table">
              <thead><tr><th>Model</th><th>Task</th><th>Kind</th><th>Trained</th><th>Status</th><th>Licence</th><th>Notes</th></tr></thead>
              <tbody>{data.models.map((m: any) => (
                <tr key={m.id}>
                  <td className="font-mono text-xs">{m.id}</td><td className="text-xs">{m.task}</td><td className="text-xs">{m.kind}</td>
                  <td>{m.trained ? <Badge tone="ok">yes</Badge> : <Badge tone="muted">no</Badge>}</td>
                  <td>{m.status === "active" ? <Badge tone="ok">active</Badge> : <Badge tone="bad">{m.status}</Badge>}</td>
                  <td className="text-xs">{m.license}</td><td className="text-xs text-navy-600">{m.notes}</td>
                </tr>
              ))}</tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  );
}
