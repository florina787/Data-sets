import { useState } from "react";
import { Link } from "react-router-dom";
import { post, waitForJob } from "../api";
import { ActionMessage, Card, Empty, Notice, Provenance, Status, Time } from "../components/ui";
import { can, roleHint, useApp } from "../context";
import { useAction, usePoll } from "../hooks";

function LatencyChart({ events }: { events: any[] }) {
  const points = events.filter((e) => e.kind === "request" && e.route?.endsWith("/checkout")).reverse();
  if (points.length === 0) return <Empty>No checkout requests in the window.</Empty>;
  const max = Math.max(5000, ...points.map((p) => p.latency_ms ?? 0));
  const w = 640, h = 140, bw = Math.max(4, Math.min(24, (w - 40) / points.length - 2));
  return (
    <figure>
      <svg viewBox={`0 0 ${w} ${h + 20}`} className="w-full" role="img" aria-label={`Checkout latency for ${points.length} requests; red bars are 5xx responses`}>
        <line x1="30" x2={w} y1={h} y2={h} stroke="#c9bfa8" />
        <text x="0" y="12" fontSize="10" fill="#3d5a8f">{Math.round(max)}ms</text>
        <text x="0" y={h} fontSize="10" fill="#3d5a8f">0</text>
        {points.map((p, i) => {
          const bh = ((p.latency_ms ?? 0) / max) * (h - 10);
          const color = p.status >= 500 ? (p.status === 503 ? "#8a5a00" : "#9b2c2c") : "#2f7d4f";
          return (
            <rect key={p.event_id} x={32 + i * (bw + 2)} y={h - bh} width={bw} height={bh} fill={color}>
              <title>{`${p.ts} ${p.status} ${p.latency_ms}ms rev ${String(p.revision).slice(0, 8)}`}</title>
            </rect>
          );
        })}
      </svg>
      <figcaption className="text-xs text-navy-600">Checkout requests in time order. Green: 2xx. Amber: 503, fails fast and the cart is kept. Red: other 5xx. Bar height is latency.</figcaption>
    </figure>
  );
}

export default function Incidents() {
  const { user, system, refreshAll } = useApp();
  const list = usePoll<any>("/api/incidents", 3000);
  const [selected, setSelected] = useState<string | null>(null);
  const current = selected ?? list.data?.incidents?.[0]?.id ?? null;
  const inc = usePoll<any>(current ? `/api/incidents/${current}` : null, 4000);
  const tel = usePoll<any>("/api/telemetry/summary", 4000);
  const fault = useAction();
  const traffic = useAction();
  const analyse = useAction();
  const [trafficResult, setTrafficResult] = useState<any>(null);
  const faultActive = system?.fault?.active;
  const a = inc.data?.analysis;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Incidents and operations</h1>
      <Card title="Operations (demo only)">
        <Notice kind="warn">The fault control is a labelled demo device. It makes the simulated inventory system wait {system?.fault?.delay_s ?? 4}s and then return 504. It does not affect anything outside this machine.</Notice>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-sm">Inventory timeout fault:</span> <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${faultActive ? "bg-brick-100 text-brick-700" : "bg-leaf-100 text-leaf-700"}`}>{faultActive ? "active" : "off"}</span> <Provenance kind="injected_fault" />
          <button className={faultActive ? "btn-ghost" : "btn-danger"} disabled={!can(user, "fault.inject") || fault.busy} title={can(user, "fault.inject") ? undefined : roleHint("fault.inject")}
            onClick={() => fault.run(async () => { await post("/api/ops/fault", { active: !faultActive }); refreshAll(); }, faultActive ? "Fault cleared. Any incident flow waiting on this resumes recovery verification." : "Fault injected.")}>
            {faultActive ? "Clear injected fault" : "Inject inventory timeout"}
          </button>
          <button className="btn-ghost" disabled={!can(user, "traffic.generate") || traffic.busy} title={can(user, "traffic.generate") ? "3 real shopper journeys against the live storefront" : roleHint("traffic.generate")}
            onClick={() => traffic.run(async () => { const { job_id } = await post("/api/ops/traffic", { journeys: 3 }); setTrafficResult(await waitForJob(job_id)); tel.refresh(); })}>
            {traffic.busy ? "Sending traffic…" : "Send synthetic shopper traffic"}
          </button>
          <button className="btn-primary" disabled={!can(user, "incident.manage") || analyse.busy} title={can(user, "incident.manage") ? "Deterministic threshold rules over recorded telemetry" : roleHint("incident.manage")}
            onClick={() => analyse.run(async () => { const { job_id } = await post("/api/incidents/analyse"); const res = await waitForJob(job_id); list.refresh(); if (res.incident) setSelected(res.incident.id); else throw new Error(res.message); }, "Incident analysis complete.")}>
            Analyse telemetry
          </button>
        </div>
        <div className="mt-2 space-y-2"><ActionMessage message={fault.message} /><ActionMessage message={traffic.message} /><ActionMessage message={analyse.message} /></div>
        {trafficResult && (
          <div className="mt-2 text-sm">Traffic on <span className="font-mono">{String(trafficResult.revision).slice(0, 10)}</span>: {JSON.stringify(trafficResult.outcomes)} · max checkout {trafficResult.max_checkout_ms} ms · carts preserved after failure: {JSON.stringify(trafficResult.carts_preserved_after_failure)}</div>
        )}
        {tel.data && <div className="mt-2 text-xs text-navy-600">All recorded telemetry: {tel.data.requests} requests, {tel.data.checkout_requests} checkouts, {tel.data.checkout_5xx} checkout 5xx, checkout p95 {tel.data.checkout_p95_ms ?? "-"} ms.</div>}
      </Card>

      {!(list.data?.incidents ?? []).length ? <Empty>No incidents. Inject the fault, send traffic, then analyse telemetry.</Empty> : (
        <Card title="Incidents">
          <div className="flex flex-wrap gap-2">
            {list.data.incidents.map((i: any) => (
              <button key={i.id} onClick={() => setSelected(i.id)} aria-pressed={i.id === current} className={`rounded-lg border px-3 py-1.5 text-sm ${i.id === current ? "border-navy-700 bg-navy-100" : "border-cream-300"}`}>
                <span className="font-mono">{i.id}</span> <Status value={i.status} /> <span className="text-xs">on {i.release_id}</span>
              </button>
            ))}
          </div>
        </Card>
      )}

      {inc.data && a && (
        <>
          <Notice kind="warn">{a.disclaimer}</Notice>
          <div className="grid gap-4 2xl:grid-cols-2">
            <Card title={<>{inc.data.id} · {inc.data.title}</>} actions={<Status value={inc.data.status} />}>
              <div className="text-sm">Release <span className="font-mono">{inc.data.release_id}</span> · revision <span className="font-mono">{inc.data.revision.slice(0, 10)}</span> · opened <Time value={inc.data.opened_at} /> · resolved <Time value={inc.data.resolved_at} /></div>
              <h3 className="label mt-3">Evidence (recorded facts)</h3>
              <ul className="mt-1 space-y-1">
                {a.evidence.map((e: any, i: number) => (
                  <li key={i} className="rounded border border-cream-200 p-2 text-sm"><Provenance kind={e.provenance} /> <span className="text-xs text-navy-600">{e.type}</span><div>{e.statement}</div></li>
                ))}
              </ul>
              <h3 className="label mt-3">Hypotheses (not proven)</h3>
              <ul className="mt-1 space-y-1">
                {a.hypotheses.map((h: any) => (
                  <li key={h.id} className="rounded border border-amber-700/30 bg-amber-100/50 p-2 text-sm">
                    <b>{h.id}</b> <span className="text-xs">({h.status})</span><div>{h.statement}</div>
                    {h.test_to_confirm && <div className="mt-1 text-xs">Confirmation: {h.test_to_confirm}</div>}
                    <div className="text-xs text-navy-600">Evidence refs: {h.evidence_refs.join(", ") || "none"}</div>
                  </li>
                ))}
              </ul>
              <h3 className="label mt-3">Standard referenced</h3>
              {a.standards.map((s: any) => <div key={s.ref} className="text-xs"><b>{s.ref}</b> {s.heading}: {s.excerpt}</div>)}
              <h3 className="label mt-3">Proposed actions</h3>
              <ul className="list-disc pl-5 text-sm">{a.proposed_actions.map((p: any) => <li key={p.action}>{p.detail}</li>)}</ul>
              <p className="mt-2 text-xs">Repair evidence (failing test on the release, passing on the candidate, gates, approval): see <Link className="underline" to="/quality">Quality</Link> and <Link className="underline" to="/releases">Release center</Link>.</p>
            </Card>
            <Card title="Telemetry timeline">
              <LatencyChart events={inc.data.timeline} />
              <div className="mt-3 max-h-72 overflow-auto">
                <table className="table">
                  <thead><tr><th>Time</th><th>Kind</th><th>Route / operation</th><th>Status</th><th>Latency</th><th>Revision</th></tr></thead>
                  <tbody>
                    {inc.data.timeline.slice(0, 120).map((e: any) => (
                      <tr key={e.event_id}>
                        <td className="text-xs"><Time value={e.ts} /></td><td className="text-xs">{e.kind}</td>
                        <td className="font-mono text-xs">{e.kind === "request" ? `${e.method} ${e.route}` : `${e.dependency}.${e.operation}`}</td>
                        <td className="text-xs">{e.status ?? e.outcome}{e.error ? ` (${e.error})` : ""}</td>
                        <td className="text-xs">{e.latency_ms} ms</td><td className="font-mono text-xs">{String(e.revision).slice(0, 8)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
