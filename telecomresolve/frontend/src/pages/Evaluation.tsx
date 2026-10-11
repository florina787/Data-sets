import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, Chip, Empty, ErrorNote } from "../components/ui";

interface Report {
  id: string; evaluated_at: string; dataset_version: string; labels_version: string; policy_version: string; kind: string;
  generation: { generation_mode: string; provider: string; model: string };
  summary: { cases: number; checks_passed: number; checks_total: number;
    per_check: Record<string, { passed: number; total: number }>;
    diagnosis_category_accuracy: { correct: number; n: number };
    assisted_action_selection: { correct: number; n: number };
    baseline_action_selection: { correct: number; n: number; description: string };
    forbidden_writes: string[]; release_gates: Record<string, boolean>; all_gates_pass: boolean };
  results: { case_id: string; scenario: string; expected_category: string | null; actual_category: string | null;
    recommended_action: string | null; baseline_action?: string; expected_terminal_state: string; actual_terminal_state: string;
    checks: Record<string, boolean> }[];
}

export function Evaluation() {
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<Report[]>("/api/evaluations").then(setReports).catch((e) => setError(e.message)); }, []);
  if (error) return <Card title="Evaluation"><ErrorNote error={error} /></Card>;
  if (!reports) return <Card title="Evaluation"><p>Loading…</p></Card>;
  if (!reports.length) return <Card title="Evaluation"><Empty>No evaluation runs recorded. Run <code>python -m app.evaluation.run</code>.</Empty></Card>;
  const r = reports[0];
  const s = r.summary;
  return (
    <div className="stack">
      <Card title={`Latest evaluation — ${r.id}`} actions={<Chip tone={s.all_gates_pass ? "ok" : "bad"}>{s.all_gates_pass ? "All release gates pass" : "Release gate failure"}</Chip>}>
        <p>{r.kind}</p>
        <dl className="kv cols">
          <dt>Evaluated</dt><dd>{r.evaluated_at}</dd>
          <dt>Dataset / labels</dt><dd>{r.dataset_version} / {r.labels_version}</dd>
          <dt>Generation</dt><dd>{r.generation.generation_mode} · {r.generation.provider} · {r.generation.model}</dd>
          <dt>Policy</dt><dd>{r.policy_version}</dd>
        </dl>
        <ul>
          {Object.entries(s.release_gates).map(([k, v]) => (
            <li key={k}><Chip tone={v ? "ok" : "bad"}>{v ? "Pass" : "Fail"}</Chip> {k.replace(/_/g, " ")}</li>
          ))}
        </ul>
        <div className="tiles">
          <div className="tile"><div className="tile-label">Checks passed</div><div className="tile-value">{s.checks_passed} / {s.checks_total}</div></div>
          <div className="tile"><div className="tile-label">Diagnosis category</div><div className="tile-value">{s.diagnosis_category_accuracy.correct} / {s.diagnosis_category_accuracy.n}</div>
            <div className="tile-sub">deterministic rules vs author labels</div></div>
          <div className="tile"><div className="tile-label">Action selection</div><div className="tile-value">{s.assisted_action_selection.correct} / {s.assisted_action_selection.n}</div>
            <div className="tile-sub">baseline heuristic: {s.baseline_action_selection.correct} / {s.baseline_action_selection.n}</div></div>
          <div className="tile"><div className="tile-label">Forbidden writes</div><div className="tile-value">{s.forbidden_writes.length}</div></div>
        </div>
        <p className="warn-note">Sample size is {s.cases} synthetic cases with labels written by the prototype author. The rules and labels
          share an author, so these results show the workflow behaves as designed; they are not evidence of diagnostic accuracy.
          Model-quality thresholds should be set only after a baseline on independently labelled data.</p>
      </Card>
      <Card title="Per case">
        <div className="table-wrap">
          <table>
            <thead><tr><th scope="col">Case</th><th scope="col">Scenario</th><th scope="col">Expected → actual category</th>
              <th scope="col">Action</th><th scope="col">Baseline</th><th scope="col">Terminal state</th><th scope="col">Checks</th></tr></thead>
            <tbody>
              {r.results.map((x) => {
                const failed = Object.entries(x.checks).filter(([, v]) => !v).map(([k]) => k);
                return (
                  <tr key={x.case_id}>
                    <td>{x.case_id}</td><td>{x.scenario}</td>
                    <td>{x.expected_category ?? "—"} → {x.actual_category ?? "—"}</td>
                    <td>{x.recommended_action ?? "none (abstained)"}</td><td>{x.baseline_action ?? "—"}</td>
                    <td>{x.expected_terminal_state} → {x.actual_terminal_state}</td>
                    <td>{failed.length ? <Chip tone="bad">{failed.join(", ")}</Chip> : <Chip tone="ok">{Object.keys(x.checks).length} pass</Chip>}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Per check">
        <div className="table-wrap">
          <table><thead><tr><th scope="col">Check</th><th scope="col">Passed</th></tr></thead>
            <tbody>{Object.entries(s.per_check).map(([k, v]) => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{v.passed} / {v.total}</td></tr>)}</tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
