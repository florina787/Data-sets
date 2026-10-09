import { useState } from "react";
import { post, waitForJob } from "../api";
import { ActionMessage, Card, Empty, Notice, Pre, Short, Status, Time } from "../components/ui";
import { can, roleHint, useApp } from "../context";
import { useAction, usePoll } from "../hooks";

export default function Releases() {
  const { user, refreshAll } = useApp();
  const list = usePoll<any>("/api/releases", 3000);
  const deployments = usePoll<any>("/api/deployments", 3000);
  const [selected, setSelected] = useState<string | null>(null);
  const releases = list.data?.releases ?? [];
  const current = selected ?? releases.find((r: any) => ["awaiting-approval", "approved", "blocked"].includes(r.status))?.id ?? releases[0]?.id ?? null;
  const rel = usePoll<any>(current ? `/api/releases/${current}` : null, 3000);
  const approve = useAction();
  const deploy = useAction();
  const rollback = useAction();
  const r = rel.data;
  const gates = r?.gates_now;
  const stale = r && r.candidate_head && r.candidate_head !== r.revision && !["deployed", "superseded", "rolled-back"].includes(r.status);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Release center</h1>
      <Card title="Releases" actions={
        <button className="btn-danger" disabled={!can(user, "release.rollback") || rollback.busy}
          title={can(user, "release.rollback") ? `Redeploys last-known-good ${list.data?.last_known_good ?? ""}` : roleHint("release.rollback")}
          onClick={() => rollback.run(async () => {
            if (!window.confirm(`Roll back to last-known-good release ${list.data?.last_known_good}?`)) return;
            const { job_id } = await post("/api/releases/rollback", { reason: "Approved rollback from release center" });
            await waitForJob(job_id); await Promise.all([list.refresh(), rel.refresh(), deployments.refresh()]); refreshAll();
          }, "Rollback deployed and health-checked.")}>
          {rollback.busy ? "Rolling back…" : "Roll back to last-known-good"}
        </button>
      }>
        <ActionMessage message={rollback.message} />
        {releases.length === 0 ? <Empty>No releases.</Empty> : (
          <div className="overflow-x-auto"><table className="table mt-2">
            <thead><tr><th /><th>Release</th><th>Kind</th><th>Revision</th><th>Status</th><th>Manifest</th><th>Deployed</th></tr></thead>
            <tbody>
              {releases.map((x: any) => (
                <tr key={x.id} className={x.id === current ? "bg-navy-100" : ""}>
                  <td><input type="radio" name="rel" aria-label={`Select ${x.id}`} checked={x.id === current} onChange={() => setSelected(x.id)} /></td>
                  <td className="font-mono text-xs">{x.id}{x.id === list.data?.current && <span className="ml-1 rounded bg-leaf-100 px-1 text-leaf-700">live</span>}{x.id === list.data?.last_known_good && <span className="ml-1 rounded bg-cream-200 px-1">LKG</span>}</td>
                  <td className="text-xs">{x.kind}</td>
                  <td><Short value={x.revision} /></td>
                  <td><Status value={x.status} /></td>
                  <td><Short value={x.manifest_hash} n={12} /></td>
                  <td className="text-xs"><Time value={x.deployed_at} /></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>

      {r && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card title={<>1 · Evidence readiness · {r.id}</>} actions={gates ? <Status value={gates.evidence_ready ? "passed" : "blocked"} /> : null}>
            {!gates ? <Empty>Seeded baseline release: no delivery-run evidence.</Empty> : (
              <ul className="space-y-1">
                {gates.gates.map((g: any) => (
                  <li key={g.id} className="flex items-start gap-2 text-sm">
                    <span aria-hidden className={g.passed ? "text-leaf-600" : "text-brick-700"}>{g.passed ? "✔" : "✖"}</span>
                    <span className="sr-only">{g.passed ? "passed" : "failed"}</span>
                    <span><span className="font-mono text-xs">{g.id}</span> {g.name}<div className="text-xs text-navy-600">{g.detail}</div></span>
                  </li>
                ))}
              </ul>
            )}
            {stale && <div className="mt-2"><Notice kind="error">The candidate head <Short value={r.candidate_head} /> differs from this manifest's revision. Approval is invalid and a new manifest is required.</Notice></div>}
          </Card>
          <Card title="2 · Deployment authorization">
            <dl className="grid grid-cols-3 gap-y-1 text-sm">
              <dt className="label">Revision</dt><dd className="col-span-2 break-all font-mono text-xs">{r.revision}</dd>
              <dt className="label">Manifest SHA-256</dt><dd className="col-span-2 break-all font-mono text-xs">{r.manifest_hash}</dd>
              <dt className="label">Approval</dt>
              <dd className="col-span-2">{r.approval ? <>approved by <b>{r.approval.approver}</b> at <Time value={r.approval.created_at} /> for <Short value={r.approval.revision} /> / <Short value={r.approval.manifest_hash} n={12} /></> : "none recorded"}</dd>
            </dl>
            <div className="mt-3 flex flex-wrap gap-2">
              <button className="btn-green" disabled={!user || approve.busy || r.status !== "awaiting-approval"}
                title={can(user, "release.approve") ? "Approves this exact revision and manifest hash" : `${roleHint("release.approve")} Try it to see the server reject it.`}
                onClick={() => approve.run(async () => { await post(`/api/releases/${r.id}/approve`, { manifest_hash: r.manifest_hash }); await Promise.all([rel.refresh(), list.refresh()]); }, "Approval recorded for this exact revision and manifest.")}>
                Approve manifest {r.manifest_hash.slice(0, 8)}
              </button>
              <button className="btn-primary" disabled={!can(user, "release.deploy") || deploy.busy || r.status !== "approved"}
                title={can(user, "release.deploy") ? "Starts the approved revision as a local process and health-checks it" : roleHint("release.deploy")}
                onClick={() => deploy.run(async () => { const { job_id } = await post(`/api/releases/${r.id}/deploy`); await waitForJob(job_id); await Promise.all([rel.refresh(), list.refresh(), deployments.refresh()]); refreshAll(); }, "Deployed and health-checked. The storefront now serves this revision.")}>
                {deploy.busy ? "Deploying…" : "Deploy to local storefront"}
              </button>
            </div>
            {!user && <p className="mt-1 text-xs text-navy-600">Sign in to act. Any signed-in role may try to approve; the server only accepts release approvers.</p>}
            <div className="mt-2 space-y-2"><ActionMessage message={approve.message} /><ActionMessage message={deploy.message} /></div>
            <details className="mt-3"><summary className="cursor-pointer text-sm">Exact manifest JSON</summary><Pre label="manifest">{JSON.stringify(r.manifest, null, 2)}</Pre></details>
          </Card>
        </div>
      )}

      <Card title="Deployments and process lifecycle">
        {!(deployments.data?.deployments ?? []).length ? <Empty>No deployments.</Empty> : (
          <table className="table">
            <thead><tr><th>Deployment</th><th>Action</th><th>Release</th><th>Revision</th><th>PID / port</th><th>Status</th><th>Lifecycle</th></tr></thead>
            <tbody>
              {deployments.data.deployments.map((d: any) => (
                <tr key={d.id}>
                  <td className="font-mono text-xs">{d.id}<div className="text-navy-600"><Time value={d.started_at} /></div></td>
                  <td className="text-xs">{d.action}<div className="text-navy-600">by {d.requested_by}</div></td>
                  <td className="text-xs">{d.release_id}</td>
                  <td><Short value={d.revision} /></td>
                  <td className="font-mono text-xs">{d.pid ?? "-"} / {d.port}</td>
                  <td><Status value={d.status} /></td>
                  <td className="text-xs">{d.lifecycle.map((l: any) => l.event).join(" → ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
