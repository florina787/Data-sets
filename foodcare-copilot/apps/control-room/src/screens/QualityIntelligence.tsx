import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card, Empty, Notice } from "../components/ui";
import { usePoll } from "../hooks";
import { AskButton } from "./Copilot";
import SupplyMap from "../components/geo/SupplyMap";

// Quality Intelligence: one dashboard over the user's own inspection records (no invented figures).

const TABS = ["Overview", "Recommendations", "Model health", "Human review"] as const;
type Tab = (typeof TABS)[number];
const GRADE_COLOUR: Record<string, string> = { Good: "#10b981", Moderate: "#f59e0b", "Not Good": "#ef4444" };

function Donut({ value, label, colour = "#38bdf8" }: { value: number | null | undefined; label: string; colour?: string }) {
  const v = value ?? 0;
  const c = 2 * Math.PI * 16;
  return (
    <div className="flex items-center gap-2">
      <svg width="44" height="44" viewBox="0 0 40 40" aria-hidden>
        <circle cx="20" cy="20" r="16" fill="none" stroke="#1e3654" strokeWidth="5" />
        <circle cx="20" cy="20" r="16" fill="none" stroke={colour} strokeWidth="5" strokeDasharray={`${c * v} ${c}`} strokeLinecap="round" transform="rotate(-90 20 20)" />
      </svg>
      <div><div className="text-xs text-navy-600">{label}</div><div className="font-mono text-sm text-navy-900">{value === null || value === undefined ? "–" : `${(v * 100).toFixed(1)}%`}</div></div>
    </div>
  );
}

function Recommendations({ rows, limit }: { rows: any[]; limit?: number }) {
  if (!rows.length) return <Empty>No inspected potatoes in this period.</Empty>;
  return (
    <table className="table">
      <thead><tr><th>Potato</th><th>Top finding</th><th>Detection score</th><th>Suggested action</th></tr></thead>
      <tbody>{rows.slice(0, limit ?? rows.length).map((r) => (
        <tr key={`${r.batch_id}-${r.potato_no}`}>
          <td><span className="font-mono text-xs">#{r.potato_no}</span> <span className="text-[11px] text-navy-600">{r.batch_id}</span>
            <div><span className="text-[11px] font-semibold" style={{ color: GRADE_COLOUR[r.grade] ?? "#94a3b8" }}>{r.grade ?? "Not graded"}</span>{r.corrected && <span className="ml-1 text-[11px] text-gold-300">corrected</span>}</div></td>
          <td className="max-w-[320px] text-xs">{r.top_finding}</td>
          <td className="w-40"><div className="flex items-center gap-2"><span className="font-mono text-xs">{r.score?.toFixed(2)}</span>
            <span className="h-1.5 flex-1 rounded-full bg-surface-line"><span className="block h-full rounded-full bg-ice-400" style={{ width: `${(r.score ?? 0) * 100}%` }} /></span></div>
            <div className="text-[10px] text-navy-600">heuristic, not calibrated</div></td>
          <td className="text-xs">{r.action}</td>
        </tr>
      ))}</tbody>
    </table>
  );
}

function Trend({ points }: { points: any[] }) {
  const [hover, setHover] = useState<number | null>(null);
  if (!points.length) return <Empty>No batches yet.</Empty>;
  const h = 120;
  const w = Math.max(points.length * 28, 200);
  const hp = hover !== null ? points[hover] : null;
  return (
    <div className="relative overflow-x-auto">
      <svg width={w} height={h + 20} role="img" aria-label="Share of potatoes graded Good per batch, oldest to newest" onMouseLeave={() => setHover(null)}>
        <line x1="0" x2={w} y1={h} y2={h} stroke="#233b58" />
        {points.map((p, i) => {
          const good = (p.good_pct ?? 0) / 100;
          return (
            <g key={p.batch_id} onMouseEnter={() => setHover(i)}>
              <rect x={i * 28 + 6} y={0} width="16" height={h} fill="transparent" />
              <rect x={i * 28 + 6} y={h - h * good} width="16" height={h * good} rx="3" fill={hover === i ? "#7dd3fc" : "#38bdf8"} />
            </g>
          );
        })}
      </svg>
      {hp && <div className="pointer-events-none absolute right-2 top-0 rounded-lg border border-surface-line bg-surface-raised px-2 py-1 text-xs" role="status">{hp.title}: <b>{hp.good_pct ?? 0}%</b> Good of {hp.detected} detected</div>}
      <p className="text-[11px] text-navy-600">Bars: share graded Good per batch, oldest → newest ({points.length} batches).</p>
    </div>
  );
}

export default function QualityIntelligence() {
  const [tab, setTab] = useState<Tab>("Overview");
  const [days, setDays] = useState("");
  const [supplier, setSupplier] = useState("");
  const qs = new URLSearchParams({ ...(days && { days }), ...(supplier && { supplier }) }).toString();
  const { data, error } = usePoll<any>(`/api/quality/overview${qs ? `?${qs}` : ""}`, 15000);
  const [updated, setUpdated] = useState(Date.now());
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (data) setUpdated(Date.now()); }, [data]);
  useEffect(() => { const id = window.setInterval(() => setNow(Date.now()), 5000); return () => window.clearInterval(id); }, []);
  const t = data?.totals;
  const det = data?.model_health?.detection;
  const gra = data?.model_health?.grading;
  const goodPct = t?.graded ? Math.round((100 * t.Good) / t.graded) : null;
  const attention = data ? [
    t.potatoes === 0 && { text: "No potatoes inspected in this period", to: "/inspection" },
    data.review.queue > 0 && { text: `${data.review.queue} Moderate/Not Good potatoes not yet reviewed`, to: "/inspection" },
    (!det || det.dataset_synthetic) && { text: "No evaluation on real labelled photos yet", to: "/evaluation" },
    (det && !det.model_trained) && { text: "Detector is rule-based (not a trained model)", to: "/evaluation" },
  ].filter(Boolean) as { text: string; to: string }[] : [];
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Quality Intelligence</h1>
          <p className="text-sm text-navy-600">Your inspection operations: recommendations, model health and human review, from stored records only.</p>
        </div>
        <div className="flex rounded-xl border border-surface-line bg-surface-card p-1" role="tablist" aria-label="Quality views">
          {TABS.map((x) => (
            <button key={x} role="tab" aria-selected={tab === x} onClick={() => setTab(x)}
              className={`rounded-lg px-3 py-1.5 text-sm transition-colors ${tab === x ? "bg-royal-600 text-white shadow-glow" : "text-navy-700 hover:text-navy-900"}`}>{x}</button>
          ))}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
        <label className="pill">Period
          <select className="bg-transparent text-navy-900" value={days} onChange={(e) => setDays(e.target.value)}>
            <option value="">All time</option><option value="1">Last 24 h</option><option value="7">Last 7 days</option><option value="30">Last 30 days</option>
          </select></label>
        <label className="pill">Supplier
          <select className="bg-transparent text-navy-900" value={supplier} onChange={(e) => setSupplier(e.target.value)}>
            <option value="">All suppliers</option>{data?.filters.suppliers.map((s: string) => <option key={s}>{s}</option>)}
          </select></label>
        <span className="pill">Updated {Math.max(0, Math.round((now - updated) / 1000))} s ago</span>
        <div className="ml-auto"><AskButton question="Which potatoes are defective?" label="Ask Jerry" /></div>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? <Empty>Loading…</Empty> : (
        <>
          {tab === "Overview" && (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              {[["Batches", t.batches], ["Potatoes inspected", t.potatoes], ["Graded Good", goodPct === null ? "–" : `${goodPct}%`], ["Review queue", data.review.queue]].map(([l, v]) => (
                <div key={l as string} className="card py-3"><div className="label">{l}</div><div className="kpi mt-1">{v}</div></div>
              ))}
            </div>
          )}
          {(tab === "Overview" || tab === "Recommendations") && (
            <Card title="Inspection recommendations" actions={<span className="text-[11px] text-navy-600">Worst first · rejection always needs a person</span>}>
              <Recommendations rows={data.recommendations} limit={tab === "Overview" ? 6 : undefined} />
            </Card>
          )}
          {(tab === "Overview" || tab === "Model health" || tab === "Human review") && (
            <div className="grid gap-4 lg:grid-cols-3">
              {(tab !== "Human review") && (
                <Card title="Model health">
                  {!det ? <Empty>No evaluation yet. <Link className="underline" to="/evaluation">Run one</Link>.</Empty> : (
                    <div className="space-y-3">
                      <div className="flex items-baseline gap-2"><span className="kpi">{det.metrics.map50?.toFixed(3)}</span><span className="text-xs text-navy-600">mAP@50</span>
                        {det.dataset_synthetic && <span className="rounded bg-amber-100 px-1.5 text-[11px] font-semibold text-amber-700">SYNTHETIC data</span>}</div>
                      <div className="grid grid-cols-2 gap-3">
                        <Donut value={det.metrics.per_class?.all?.precision50} label="Precision" />
                        <Donut value={det.metrics.per_class?.all?.recall50} label="Recall" />
                        <Donut value={det.metrics.counting?.exact_count_accuracy} label="Exact count" colour="#e9b95b" />
                        <Donut value={gra?.metrics.accuracy} label="Grade accuracy" colour="#10b981" />
                      </div>
                      <p className="text-[11px] text-navy-600">{det.model_id} on {det.dataset_id} · {det.sample_size} images · {new Date(det.created_at).toLocaleString()}</p>
                    </div>
                  )}
                </Card>
              )}
              {(tab !== "Model health") && (
                <Card title="Human in the loop">
                  <div className="grid grid-cols-3 gap-2">
                    <div><div className="label">Review queue</div><div className="kpi">{data.review.queue}</div></div>
                    <div><div className="label">Corrections</div><div className="kpi">{data.review.corrections}</div></div>
                    <div><div className="label">Rules kept</div><div className="kpi">{data.review.rules_agreement_pct ?? "–"}{data.review.rules_agreement_pct !== null && "%"}</div></div>
                  </div>
                  <p className="mt-2 text-[11px] text-navy-600">{data.review.note}</p>
                </Card>
              )}
              <Card title="Needs attention">
                {attention.length === 0 ? <Empty>Nothing needs attention.</Empty> : (
                  <ul className="space-y-1.5 text-sm">{attention.map((a) => (
                    <li key={a.text}><Link to={a.to} className="flex items-center gap-2 rounded-lg px-2 py-1 hover:bg-surface-raised"><span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden />{a.text}</Link></li>
                  ))}</ul>
                )}
              </Card>
            </div>
          )}
          {(tab === "Overview" || tab === "Model health") && (
            <Card title="Quality trend"><Trend points={data.trend} /></Card>
          )}
        </>
      )}
      <SupplyMap title="Geographic quality incidents" defaultTab="quality" defaultOverlay="risk" />
    </div>
  );
}
