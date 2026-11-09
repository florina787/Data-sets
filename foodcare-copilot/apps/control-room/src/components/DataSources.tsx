import { Link } from "react-router-dom";
import { usePoll } from "../hooks";
import { PotatoOrbit } from "./Illustrations";

type Source = { key: string; name: string; kind: string; status: string; records: number; unit: string; detail: string; to: string | null; needs: string | null };

const STATUS: Record<string, { label: string; cls: string; dot: string }> = {
  connected: { label: "Connected", cls: "border-emerald-500/40", dot: "bg-emerald-500" },
  synthetic: { label: "Synthetic demo data", cls: "border-gold-400/40", dot: "bg-gold-400" },
  empty: { label: "Connected · no records yet", cls: "border-ice-400/30", dot: "bg-ice-400" },
  not_connected: { label: "Not connected", cls: "border-dashed border-surface-line opacity-70", dot: "bg-navy-600" },
};

function SourceCard({ s }: { s: Source }) {
  const st = STATUS[s.status] ?? STATUS.not_connected;
  const body = (
    <div className={`h-full rounded-xl border bg-surface-raised/50 p-3 transition-colors hover:bg-surface-raised ${st.cls}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-navy-900">{s.name}</span>
        <span className="label">{s.kind}</span>
      </div>
      <div className="mt-1 flex items-baseline gap-1.5">
        {s.status !== "not_connected" && <span className="kpi text-xl">{s.records.toLocaleString()}</span>}
        {s.status !== "not_connected" && <span className="text-xs text-navy-600">{s.unit}</span>}
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-navy-700"><span className={`h-1.5 w-1.5 rounded-full ${st.dot}`} aria-hidden />{st.label}</div>
      <p className="mt-1 text-xs text-navy-600">{s.detail}</p>
      {s.needs && <p className="mt-1 text-xs text-gold-300">Needs: {s.needs}</p>}
    </div>
  );
  return s.to ? <Link to={s.to} className="block h-full">{body}</Link> : body;
}

/** Every potato data source feeding the copilot, with live counts and honest status. */
export function PotatoDataSources() {
  const { data, error } = usePoll<{ sources: Source[] }>("/api/data-sources", 20000);
  const all = data?.sources ?? [];
  const live = all.filter((s) => (s.status === "connected" || s.status === "empty") && s.key !== "conversations");
  const synthetic = all.filter((s) => s.status === "synthetic");
  const right = [...synthetic, ...all.filter((s) => s.key === "conversations")];
  const planned = all.filter((s) => s.status === "not_connected");
  const connected = all.filter((s) => s.status === "connected").length;
  return (
    <section className="card" aria-labelledby="sources-title">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="sources-title" className="text-lg font-semibold">Potato data sources</h2>
          <p className="text-sm text-navy-600">Everything Jerry can draw on, with live record counts. Grey cards are planned sources with no integration yet; nothing is simulated for them.</p>
        </div>
        {!data && <span className="pill">{error ? "Sign in to see live record counts" : "Loading…"}</span>}
        {data && <span className="pill">{connected} with data · {synthetic.length} synthetic · {planned.length} not connected</span>}
      </div>
      <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto_1fr] lg:items-center">
        <div className="grid gap-3 sm:grid-cols-2">{live.map((s) => <SourceCard key={s.key} s={s} />)}</div>
        <div className="flex flex-col items-center gap-1 px-2 py-4">
          <PotatoOrbit />
          <span className="text-xs text-navy-600">All sources flow into Jerry's cited answers</span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">{right.map((s) => <SourceCard key={s.key} s={s} />)}</div>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{planned.map((s) => <SourceCard key={s.key} s={s} />)}</div>
    </section>
  );
}
