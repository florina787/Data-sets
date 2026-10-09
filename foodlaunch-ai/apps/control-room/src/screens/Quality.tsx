import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, Empty, Notice, Pre, Short, Status, Time } from "../components/ui";
import { useApp } from "../context";
import { usePoll } from "../hooks";

export default function Quality() {
  const { runId } = useApp();
  const detail = usePoll<any>(runId ? `/api/runs/${runId}` : null, 4000);
  const [selected, setSelected] = useState<string | null>(null);
  const [tr, setTr] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const runs = detail.data?.test_runs ?? [];
  const current = selected ?? runs[0]?.id ?? null;

  useEffect(() => {
    if (!current) return;
    api(`/api/test-runs/${current}`).then((d) => { setTr(d); setErr(null); }).catch((e) => setErr(e.message));
  }, [current]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Quality</h1>
      {!runId ? <Empty>No run selected.</Empty> : runs.length === 0 ? <Empty>No test runs yet.</Empty> : (
        <>
          <Card title="Test runs (real pytest executions)">
            <table className="table">
              <thead><tr><th /><th>Test run</th><th>Purpose</th><th>Revision</th><th>Suite</th><th>Exit code</th><th>Status</th><th>Duration</th><th>Started</th></tr></thead>
              <tbody>
                {runs.map((t: any) => (
                  <tr key={t.id} className={t.id === current ? "bg-navy-100" : ""}>
                    <td><input type="radio" name="tr" aria-label={`Select ${t.id}`} checked={t.id === current} onChange={() => setSelected(t.id)} /></td>
                    <td className="font-mono text-xs">{t.id}</td>
                    <td className="text-xs">{t.purpose}</td>
                    <td><Short value={t.revision} /></td>
                    <td className="text-xs">v{t.suite_version} · <Short value={t.tests_hash} n={8} /></td>
                    <td className="font-mono">{t.exit_code}</td>
                    <td><Status value={t.status} /></td>
                    <td className="text-xs">{t.duration_s}s</td>
                    <td className="text-xs"><Time value={t.started_at} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="mt-2 text-xs text-navy-600">The same protected test files (hash-checked against the approved plan) run against each exact revision. A pass on an old revision never qualifies a new one.</p>
          </Card>
          {err && <Notice kind="error">{err}</Notice>}
          {tr && (
            <div className="grid gap-4 2xl:grid-cols-2">
              <Card title={<>Results · {tr.test_run.id}</>} actions={<Status value={tr.test_run.status} />}>
                <table className="table">
                  <thead><tr><th>Test</th><th>Outcome</th><th>Criteria</th></tr></thead>
                  <tbody>
                    {tr.results.map((r: any) => (
                      <tr key={r.nodeid}>
                        <td className="break-all font-mono text-xs">{r.nodeid.split("::").slice(1).join("::")}<div className="text-[10px] text-navy-600">{r.nodeid.split("::")[0]}</div></td>
                        <td><Status value={r.outcome} /></td>
                        <td className="text-xs">{r.ac_ids.join(", ")} {r.regression_ids.map((g: string) => <span key={g} className="ml-1 rounded bg-navy-100 px-1">{g}</span>)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
              <Card title="Captured output">
                <div className="mb-2 text-xs text-navy-600">Command: <code className="mono">{tr.test_run.command}</code> · exit code {tr.test_run.exit_code}</div>
                <Pre label="pytest output">{tr.test_run.output}</Pre>
              </Card>
            </div>
          )}
          <Card title="Static checks (Review Agent)">
            {!(detail.data?.static_checks ?? []).length ? <Empty>No static checks yet.</Empty> : (
              <table className="table">
                <thead><tr><th>Check</th><th>Tool</th><th>Revision</th><th>Exit code</th><th>Status</th><th>Findings</th></tr></thead>
                <tbody>
                  {detail.data.static_checks.map((c: any) => (
                    <tr key={c.id}><td className="font-mono text-xs">{c.id}</td><td>{c.tool}</td><td><Short value={c.revision} /></td><td className="font-mono">{c.exit_code}</td><td><Status value={c.status} /></td><td className="text-xs">{JSON.parse(c.findings_json).length}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="mt-2 text-xs text-navy-600">Ruff runs with a policy config owned by the platform, plus an AST scan for forbidden calls and imports. These are automated checks, not a security certification.</p>
          </Card>
        </>
      )}
    </div>
  );
}
