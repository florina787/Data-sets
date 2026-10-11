import { useEffect, useState } from "react";
import { api } from "../api";
import { useApp } from "../App";
import { Action, Badge, Card, ErrorBox } from "../components";
import { ci, pct, pp, shortDigest, when } from "../format";
import type { TabProps } from "./ChangePage";
import { GateTable } from "./tabs";

function Compare({ name, b }: { name: string; b: any }) {
  const rows: [string, string][] = [["top1", "Top-1 accuracy (primary)"], ["top3", "Top-3 accuracy (secondary)"]];
  return (
    <div className="table-wrap">
      <table data-testid={`compare-${name}`}>
        <thead><tr><th>{name}</th><th className="num">Baseline</th><th className="num">Candidate</th><th className="num">Δ (pp)</th></tr></thead>
        <tbody>
          {rows.map(([k, label]) => (
            <tr key={k}><td>{label}</td>
              <td className="num">{b.baseline[`${k}_correct`]}/{b.baseline.n_eligible} = {pct(b.baseline[`${k}_accuracy_pct`])}<div className="small muted">95% {b.baseline[`${k}_wilson95`][0]}–{b.baseline[`${k}_wilson95`][1]}%</div></td>
              <td className="num">{b.candidate[`${k}_correct`]}/{b.candidate.n_eligible} = {pct(b.candidate[`${k}_accuracy_pct`])}<div className="small muted">95% {b.candidate[`${k}_wilson95`][0]}–{b.candidate[`${k}_wilson95`][1]}%</div></td>
              <td className="num"><strong>{pp(b.delta[`${k}_delta_pp`])}</strong>{k === "top1" && <div className="small muted">paired 95% CI {ci(b.delta_ci95_pp)}</div>}</td></tr>
          ))}
          <tr><td>Coverage (answered / eligible)</td><td className="num">{b.baseline.answered}/{b.baseline.n_eligible} = {pct(b.baseline.coverage_pct)}</td>
            <td className="num">{b.candidate.answered}/{b.candidate.n_eligible} = {pct(b.candidate.coverage_pct)}</td><td className="num">{pp(b.delta.coverage_delta_pp)}</td></tr>
          <tr><td>Abstentions (kept in denominator)</td><td className="num">{b.baseline.abstained} ({pct(b.baseline.abstention_rate_pct)})</td>
            <td className="num">{b.candidate.abstained} ({pct(b.candidate.abstention_rate_pct)})</td><td></td></tr>
          <tr><td>Conditional top-1 on answered only</td><td className="num">{pct(b.baseline.conditional_top1_accuracy_pct)}</td>
            <td className="num">{pct(b.candidate.conditional_top1_accuracy_pct)}</td><td className="num">{pp(b.delta.conditional_top1_delta_pp)}</td></tr>
          <tr><td>Relative change of top-1 (not pp)</td><td></td><td></td><td className="num">{b.delta.top1_relative_change_pct > 0 ? "+" : ""}{b.delta.top1_relative_change_pct}%</td></tr>
        </tbody>
      </table>
    </div>
  );
}

function Confusion({ c, title }: { c: any; title: string }) {
  return (
    <div className="table-wrap" style={{ flex: 1, minWidth: 260 }}>
      <table>
        <caption className="small" style={{ textAlign: "left" }}>{title}</caption>
        <thead><tr><th>ref \ pred</th>{c.cols.map((x: string) => <th key={x} className="num">{x}</th>)}</tr></thead>
        <tbody>{c.rows.map((r: string) => <tr key={r}><th>{r}</th>{c.cols.map((x: string) => <td key={x} className="num">{c.counts[r][x] || ""}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

export default function EvaluationTab({ d, reload }: TabProps) {
  const { me } = useApp();
  const runs = d.evaluation_runs;
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<any>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [samples, setSamples] = useState<any[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const id = runId ?? runs[runs.length - 1]?.id;
  useEffect(() => { if (id) api(`/api/evaluations/${id}`).then((r) => { setRun(r); setErr(null); }).catch(setErr); }, [id, d]);
  useEffect(() => { setSamples(null); }, [sel, id]);
  if (!runs.length) return <Card title="Evaluation"><p className="muted">No evaluation yet. Register a candidate and run an evaluation from the Development tab.</p></Card>;
  const s = run?.summary;
  const target = s?.target_cell;
  const thr = s?.thresholds;
  const strata = s?.config?.strata ?? [];
  const lighting = s?.config?.lighting ?? [];
  const cell = sel && s ? s.cells[sel] : null;
  return (
    <div>
      <ErrorBox error={err} />
      <Card title="Evaluation runs">
        <table><thead><tr><th>Run</th><th>Candidate</th><th>Status</th><th>Outcome</th><th>Finished</th><th className="num">ms</th></tr></thead>
          <tbody>{runs.map((r: any) => (
            <tr key={r.id} style={{ fontWeight: r.id === id ? 700 : 400 }}>
              <td><button className="link" onClick={() => setRunId(r.id)}>{r.id}</button></td><td><code>{r.candidate_model_id}</code></td>
              <td><Badge s={r.status} /></td><td><Badge s={r.outcome ?? "PENDING"} label={r.outcome ?? "—"} /></td><td className="small">{when(r.finished_at)}</td><td className="num">{r.duration_ms ?? ""}</td></tr>
          ))}</tbody></table>
        {run && ["QUEUED", "RUNNING"].includes(run.status) && can(me) && <Action label="Cancel evaluation" run={() => api(`/api/evaluations/${run.id}/cancel`, { method: "POST" })} onDone={reload} />}
        {run?.error && <div className="error">Computation error ({run.error.category}): {run.error.message}</div>}
      </Card>
      {s && <>
        <Card title={<>Outcome <Badge s={run.outcome} /></>}>
          <p className="small">{run.candidate_model_id} vs {run.baseline_model_id} on <strong>{s.eligible_total}</strong> eligible paired held-out samples (of {s.split_total}; excluded {Object.entries(s.exclusions).map(([k, v]) => `${k}: ${v}`).join(", ")}).
            Prediction mode: <strong>{s.prediction_mode === "synthetic_fixture" ? "synthetic fixtures — not computer-vision inference" : s.prediction_mode}</strong>. Policy {s.policy_version}; config {run.evaluation_config_id}; candidate digest <code title={run.candidate_artifact_digest}>{shortDigest(run.candidate_artifact_digest)}</code>. Test-split evaluation #{s.test_set_evaluation_index} for this change.</p>
          <GateTable gates={s.gates} />
          <p className="small muted">Thresholds in effect: min {thr.min_samples_per_cell} samples/cell, max regression {thr.max_regression_pp} pp, target ≥ +{thr.target_min_improvement_pp} pp, coverage drop ≤ {thr.max_coverage_drop_pp} pp (illustrative demo rules). A favourable summary cannot change these computed results.</p>
        </Card>
        <Card title="Overall (aggregate)"><Compare name="Overall" b={s.overall} /></Card>
        <Card title="Required cells: top-1 Δ vs baseline (pp)">
          <p className="small muted">Click a cell for details. Labels show Δ, n and status in text; colour is secondary. Outlined cell = target.</p>
          <div className="cellgrid" role="grid" aria-label="Evaluation cells">
            <div className="h">stratum</div>{lighting.map((l: string) => <div className="h" key={l}>{l}</div>)}
            {strata.map((st: string) => [
              <div className="h" key={st}>{st}</div>,
              ...lighting.map((l: string) => {
                const k = `${st}|${l}`; const c = s.cells[k];
                if (!c) return <div key={k} className="cell">no data</div>;
                const dlt = c.delta.top1_delta_pp;
                const bad = dlt < -thr.max_regression_pp || c.baseline.n_eligible < thr.min_samples_per_cell;
                return (
                  <button key={k} className={`cell ${bad ? "bad" : dlt > 0 ? "good" : ""} ${k === target ? "target" : ""} ${sel === k ? "sel" : ""}`}
                    onClick={() => setSel(k)} data-testid={`cell-${k}`} aria-pressed={sel === k}>
                    <div className="d">{pp(dlt)}</div>
                    <div className="small">{c.baseline.top1_accuracy_pct}% → {c.candidate.top1_accuracy_pct}% · n={c.baseline.n_eligible}</div>
                    <div className="small">{bad ? "✕ beyond limit" : k === target ? "◎ target" : "✓ within limit"}</div>
                  </button>
                );
              }),
            ])}
          </div>
        </Card>
        {cell && <Card title={<>Cell <code>{sel}</code>{sel === target ? " (target)" : ""}</>}>
          <Compare name={sel!} b={cell} />
          <div className="row" style={{ alignItems: "flex-start", marginTop: 8 }}>
            <Confusion c={cell.baseline_confusion} title="Baseline: reference family × predicted family" />
            <Confusion c={cell.candidate_confusion} title="Candidate: reference family × predicted family" />
          </div>
          <p className="small muted">Shade IDs are catalogue identifiers. No perceptual colour distance is computed — that needs measured references and an agreed colorimetric protocol.</p>
          <button onClick={async () => setSamples((await api(`/api/evaluations/${run.id}/predictions?cell=${encodeURIComponent(sel!)}&limit=20`)).rows)}>Show sample-level fixture predictions</button>
          {samples && <table><thead><tr><th>Sample</th><th>Model</th><th>Expected</th><th>Top-3</th><th>Device</th></tr></thead>
            <tbody>{samples.map((r, i) => <tr key={i}><td><code>{r.sample_id}</code></td><td className="small">{r.model_id}</td><td>{r.expected}</td><td>{r.abstained ? "ABSTAINED" : r.top3.join(", ")}</td><td>{r.device}</td></tr>)}</tbody></table>}
        </Card>}
        <Card title="Privacy and authorization control tests (executed during evaluation)">
          <table><thead><tr><th>Test</th><th>Kind</th><th>Status</th><th>Observed</th></tr></thead>
            <tbody>{s.controls.map((c: any) => <tr key={c.test_id}><td><code>{c.test_id}</code></td><td>{c.kind}</td><td><Badge s={c.status} /></td><td className="small">{c.observed}</td></tr>)}</tbody></table>
        </Card>
        {d.evaluation_interpretation && d.evaluation_interpretation.data && <Card title="Evaluation agent interpretation">
          <p className="small muted">{d.evaluation_interpretation.data.note}</p>
          <ul>{d.evaluation_interpretation.data.findings.map((f: string) => <li key={f}>{f}</li>)}</ul>
          <h3>Limitations</h3>
          <ul className="small">{d.evaluation_interpretation.data.limitations.map((f: string) => <li key={f}>{f}</li>)}</ul>
          <p className="small">Uncertainty: {s.uncertainty_method}. Label validity and statistical uncertainty still require expert review.</p>
        </Card>}
      </>}
    </div>
  );
}

function can(me: any) { return !!me?.permissions?.includes("evaluation.cancel"); }
