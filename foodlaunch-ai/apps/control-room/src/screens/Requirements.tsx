import { Link } from "react-router-dom";
import { post } from "../api";
import { ActionMessage, Card, Empty, Notice, Provenance, Short, Status } from "../components/ui";
import { can, roleHint, useApp } from "../context";
import { useAction, usePoll } from "../hooks";

export default function Requirements() {
  const { runId, user } = useApp();
  const detail = usePoll<any>(runId ? `/api/runs/${runId}` : null, 4000);
  const trace = usePoll<any>(runId ? `/api/runs/${runId}/trace` : null, 4000);
  const action = useAction();
  if (!runId) return <Empty>No run selected.</Empty>;
  const sets = detail.data?.requirement_sets ?? [];
  const decisions = Object.fromEntries((detail.data?.clarifications ?? []).map((c: any) => [c.id, c]));
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Requirements and traceability</h1>
      {detail.error && <Notice kind="error">{detail.error}</Notice>}
      {sets.length === 0 ? <Empty>No requirement set yet. Requirements are drafted after the clarification decisions are recorded.</Empty> : (
        <Card title="Requirement set versions">
          <table className="table">
            <thead><tr><th>Version</th><th>Status</th><th>Origin</th><th>Source</th><th>Frozen test plan</th><th /></tr></thead>
            <tbody>
              {sets.map((s: any) => (
                <tr key={s.version}>
                  <td>v{s.version}</td>
                  <td><Status value={s.status} />{s.approved_by && <div className="text-xs text-navy-600">by {s.approved_by}</div>}</td>
                  <td><Provenance kind={s.origin === "live_ai" ? "live_ai" : "fixture"} /> <span className="text-xs">{s.origin}</span></td>
                  <td className="text-xs">{s.source}</td>
                  <td className="text-xs">{s.test_plan.files.join(", ") || "none (not linked to executable tests)"}{s.test_plan.tests_hash && <div>hash <Short value={s.test_plan.tests_hash} n={12} /></div>}</td>
                  <td>
                    {s.status !== "approved" && (
                      <button className="btn-green" disabled={!can(user, "requirements.approve") || action.busy}
                        title={can(user, "requirements.approve") ? "Approving freezes the protected test plan hashes" : roleHint("requirements.approve")}
                        onClick={() => action.run(async () => { await post(`/api/runs/${runId}/requirements/${s.version}/approve`); detail.refresh(); trace.refresh(); }, `Requirement set v${s.version} approved; test plan frozen. Use Continue on the board to resume the agents.`)}>
                        Approve v{s.version}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2"><ActionMessage message={action.message} /></div>
        </Card>
      )}
      {trace.data && trace.data.requirements.length > 0 && (
        <Card title={<>Requirement detail · set v{trace.data.requirement_set_version} · candidate head <Short value={trace.data.head_revision} /></>}>
          <p className="mb-3 text-xs text-navy-600">Chain: brief v{trace.data.brief.version} → requirement → acceptance criterion → change set → test result (exact revision) → release → incident → repair. A missing link is shown as a gap.</p>
          <div className="space-y-3">
            {trace.data.requirements.map((r: any) => (
              <details key={r.req_id} className="rounded-lg border border-cream-300 p-3" open>
                <summary className="cursor-pointer">
                  <span className="font-mono text-xs font-semibold">{r.req_id}</span> <span className="font-semibold">{r.title}</span>
                  <span className="ml-2 text-xs text-navy-600">decisions: {r.decisions.map((d: string) => `${d} (${decisions[d]?.decision ?? "?"})`).join("; ") || "none"}</span>
                </summary>
                <div className="mt-1 text-xs">Change sets: {r.change_sets.length ? r.change_sets.map((c: string) => <Link key={c} to="/engineering" className="mr-2 font-mono underline">{c}</Link>) : <span className="text-brick-700">gap: none</span>}</div>
                <table className="table mt-2">
                  <thead><tr><th>AC</th><th>Criterion</th><th>On head revision</th><th>Linked tests (all revisions)</th></tr></thead>
                  <tbody>
                    {r.criteria.map((a: any) => (
                      <tr key={a.ac_id}>
                        <td className="font-mono text-xs">{a.ac_id}{a.critical && <div className="text-[10px] text-navy-600">critical</div>}</td>
                        <td className="text-xs">{a.text}</td>
                        <td><span className={`text-xs font-semibold ${a.status_on_head === "passing" ? "text-leaf-700" : "text-brick-700"}`}>{a.status_on_head}</span></td>
                        <td className="text-xs">
                          {a.tests.length === 0 ? <span className="text-brick-700">gap: no test</span> :
                            Object.values(a.tests.reduce((acc: any, t: any) => { (acc[t.nodeid] ??= []).push(t); return acc; }, {})).map((ts: any) => (
                              <div key={ts[0].nodeid} className="mb-0.5">
                                <span className="font-mono">{ts[0].nodeid.split("::")[1]}</span>{" "}
                                {ts.map((t: any) => <span key={t.test_run_id} className={`mr-1 rounded px-1 ${t.outcome === "passed" ? "bg-leaf-100 text-leaf-700" : "bg-brick-100 text-brick-700"}`} title={`${t.test_run_id} @ ${t.revision}`}>{t.outcome} @{t.revision.slice(0, 7)}</span>)}
                                {ts[0].regression_ids.map((g: string) => <span key={g} className="rounded bg-navy-100 px-1">{g}</span>)}
                              </div>
                            ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            ))}
          </div>
          <div className="mt-3 grid gap-3 text-xs md:grid-cols-2">
            <div><div className="label">Releases</div>{trace.data.releases.map((r: any) => <div key={r.id}>{r.id} <Status value={r.status} /> {r.kind} <Short value={r.revision} /> {r.incident_id && `← ${r.incident_id}`}</div>)}{!trace.data.releases.length && "none"}</div>
            <div><div className="label">Incidents</div>{trace.data.incidents.map((i: any) => <div key={i.id}>{i.id} <Status value={i.status} /> on {i.release_id}</div>)}{!trace.data.incidents.length && "none"}</div>
          </div>
        </Card>
      )}
    </div>
  );
}
