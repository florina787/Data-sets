import { useEffect, useState } from "react";
import { api } from "../api";
import { Card, DiffView, Empty, Notice, Provenance, Short } from "../components/ui";
import { useApp } from "../context";
import { usePoll } from "../hooks";

export default function Engineering() {
  const { runId } = useApp();
  const detail = usePoll<any>(runId ? `/api/runs/${runId}` : null, 5000);
  const log = usePoll<any>("/api/repository/log", 8000);
  const [selected, setSelected] = useState<string | null>(null);
  const [cs, setCs] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const sets = detail.data?.change_sets ?? [];
  const current = selected ?? sets[0]?.id ?? null;

  useEffect(() => {
    if (!current) return;
    setErr(null);
    api(`/api/change-sets/${current}`).then(setCs).catch((e) => setErr(e.message));
  }, [current]);

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Engineering</h1>
      {!runId ? <Empty>No run selected.</Empty> : sets.length === 0 ? <Empty>No change sets yet. The Implementation Agent applies patches after requirements are approved.</Empty> : (
        <div className="grid gap-4 lg:grid-cols-4">
          <Card title="Change sets" className="lg:col-span-1">
            <ul className="space-y-2">
              {sets.map((c: any) => (
                <li key={c.id}>
                  <button className={`w-full rounded-lg border p-2 text-left text-sm ${c.id === current ? "border-navy-700 bg-navy-100" : "border-cream-300 hover:bg-cream-50"}`} onClick={() => setSelected(c.id)} aria-pressed={c.id === current}>
                    <div className="font-mono text-xs">{c.id} · {c.kind}</div>
                    <div className="font-medium">{c.title}</div>
                    <div className="text-xs text-navy-600">{c.agent} · <span className="text-leaf-700">+{c.diff_stats.added}</span> <span className="text-brick-700">-{c.diff_stats.removed}</span></div>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
          <div className="space-y-4 lg:col-span-3">
            {err && <Notice kind="error">{err}</Notice>}
            {cs && (
              <Card title={cs.title} actions={<Provenance kind="fixture" />}>
                <dl className="mb-3 grid grid-cols-2 gap-x-4 gap-y-1 text-sm md:grid-cols-4">
                  <dt className="label">Base revision</dt><dd><Short value={cs.base_revision} n={12} /></dd>
                  <dt className="label">Candidate revision</dt><dd><Short value={cs.revision} n={12} /></dd>
                  <dt className="label">Patch</dt><dd className="mono">{cs.patch_name}</dd>
                  <dt className="label">Patch SHA-256</dt><dd><Short value={cs.patch_hash} n={16} /></dd>
                  <dt className="label">Agent</dt><dd>{cs.agent}</dd>
                  <dt className="label">Addresses</dt><dd className="text-xs">{cs.addresses.join(", ")}</dd>
                  <dt className="label">Files</dt><dd className="col-span-3 font-mono text-xs">{cs.files.join(", ")}</dd>
                </dl>
                <Notice kind="warn">Fixture proposal: a seeded patch, applied with <code>git apply</code> to the run's isolated git worktree and committed. This diff is the real <code>git diff base..candidate</code> output.</Notice>
                <div className="mt-3"><DiffView diff={cs.diff_text} /></div>
              </Card>
            )}
          </div>
        </div>
      )}
      <Card title="Storefront repository (all branches)">
        {!log.data ? <Empty>Loading…</Empty> : (
          <table className="table">
            <thead><tr><th>Revision</th><th>Date</th><th>Subject</th></tr></thead>
            <tbody>{log.data.commits.map((c: any) => <tr key={c.revision}><td><Short value={c.revision} n={12} /></td><td className="text-xs">{c.date}</td><td className="text-sm">{c.subject}</td></tr>)}</tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
