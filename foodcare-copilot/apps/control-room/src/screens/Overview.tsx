import { Link } from "react-router-dom";
import { DemoControls } from "../components/Layout";
import { Card, Empty, Notice, Short, Status, Time } from "../components/ui";
import { useApp } from "../context";
import { usePoll } from "../hooks";

function Metric({ label, value, unit }: { label: string; value: any; unit?: string }) {
  return (
    <div className="rounded-lg border border-cream-300 bg-cream-50 p-3">
      <div className="text-xs text-navy-600">{label}</div>
      <div className="mt-1 text-xl font-semibold text-navy-900">
        {value ?? <span className="text-sm text-navy-600">no data</span>}
        {value != null && unit && <span className="ml-1 text-sm font-normal text-navy-600">{unit}</span>}
      </div>
    </div>
  );
}

function stepResult(step: any): string {
  if (step.error) return step.error;
  if (!step.result) return "";
  return Object.entries(step.result)
    .filter(([, v]) => typeof v !== "object")
    .map(([k, v]) => `${k}: ${v}`)
    .join(" · ");
}

export default function Overview() {
  const { data, error } = usePoll<any>("/api/overview", 3000);
  const { demo } = useApp();
  const m = data?.metrics;
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">Delivery overview</h1>
          <p className="text-sm text-navy-600">Marketing-driven digital changes, from brief to monitored release.</p>
        </div>
      </div>
      {error && <Notice kind="error">Could not load overview: {error}</Notice>}

      <Card title="Guided demo" actions={<div className="rounded-lg bg-navy-900 p-1"><DemoControls compact /></div>}>
        <p className="mb-3 text-sm text-navy-600">
          Each step signs in as a demo account and calls the same APIs as the screens. It waits for real tests,
          git operations, deployments and HTTP traffic to finish, then checks the actual outcome against the expected one.
        </p>
        <ol className="space-y-1.5">
          {(demo?.steps ?? []).map((s: any, i: number) => (
            <li key={s.id} className="flex flex-wrap items-start gap-2 rounded-md border border-cream-200 px-2 py-1.5 text-sm">
              <span className="w-6 text-right font-mono text-navy-600">{i + 1}.</span>
              <Status value={s.status} />
              <span className="font-medium">{s.title}</span>
              <span className="text-xs text-navy-600">· {s.actor}</span>
              {stepResult(s) && <span className={`basis-full pl-8 text-xs ${s.error ? "text-brick-700" : "text-navy-600"}`}>{stepResult(s)}</span>}
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Active work">
          {!data ? <Empty>Loading…</Empty> : data.runs.length === 0 ? (
            <Empty>No delivery runs yet. Submit a brief or run the guided demo.</Empty>
          ) : (
            <table className="table">
              <thead><tr><th>Run</th><th>Status</th><th>Stage</th><th>Waiting for</th></tr></thead>
              <tbody>
                {data.runs.map((r: any) => (
                  <tr key={r.id}>
                    <td><Link className="font-mono text-xs underline" to="/board">{r.id}</Link><div className="text-xs text-navy-600">{r.title} · {r.mode}</div></td>
                    <td><Status value={r.status} /></td>
                    <td className="text-xs">{r.stage}</td>
                    <td className="text-xs">{r.waiting_for?.replaceAll("_", " ") ?? (r.error ? <span className="text-brick-700">{r.error}</span> : "-")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
        <Card title="Releases and incidents">
          <div className="space-y-3 text-sm">
            <div>
              <div className="label">Current release</div>
              {data?.current_release ? (
                <div className="flex flex-wrap items-center gap-2">{data.current_release.id} <Short value={data.current_release.revision} /> <Status value={data.current_release.status} /> <span className="text-xs text-navy-600">{data.current_release.kind}</span></div>
              ) : <span className="text-navy-600">none</span>}
              <div className="text-xs text-navy-600">Last known good: {data?.last_known_good ?? "-"}</div>
            </div>
            <div>
              <div className="label">Releases needing attention</div>
              {data?.blocked_releases?.length ? data.blocked_releases.map((r: any) => (
                <div key={r.id} className="flex items-center gap-2"><Link to="/releases" className="underline">{r.id}</Link> <Status value={r.status} /> <Short value={r.revision} /></div>
              )) : <span className="text-navy-600">none</span>}
            </div>
            <div>
              <div className="label">Open incidents</div>
              {data?.incidents?.length ? data.incidents.map((i: any) => (
                <div key={i.id} className="flex items-center gap-2"><Link to="/incidents" className="underline">{i.id}</Link> <Status value={i.status} /> {i.title} <Time value={i.opened_at} /></div>
              )) : <span className="text-navy-600">none</span>}
            </div>
          </div>
        </Card>
      </div>

      <Card title="Measured run metrics">
        <p className="mb-3 text-xs text-navy-600">{m?.label ?? "Computed from recorded test runs, deployments, audit events and telemetry in this installation."} No business ROI or time-savings figures are claimed.</p>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Metric label="Test runs (passed / failed)" value={m ? `${m.test_runs_passed} / ${m.test_runs_failed}` : null} />
          <Metric label="Median test run" value={m?.median_test_run_s} unit="s" />
          <Metric label="Deployments (rollbacks)" value={m ? `${m.deployments} (${m.rollbacks})` : null} />
          <Metric label="Median deploy + health check" value={m?.median_deploy_s} unit="s" />
          <Metric label="Rejected actions (audit)" value={m?.gate_rejections} />
          <Metric label="Checkout p95 (all telemetry)" value={m?.checkout_p95_ms} unit="ms" />
        </div>
        {m?.brief_to_first_deploy_s != null && (
          <p className="mt-2 text-xs text-navy-600">Wall-clock time from brief submission to first healthy deployment in this demo run: {m.brief_to_first_deploy_s}s. This includes scripted human steps, so it is not a productivity claim.</p>
        )}
      </Card>
    </div>
  );
}
