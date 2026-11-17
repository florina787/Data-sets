import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { pct, pctPlain, tone } from "../lib/format";
import { ErrorBox, KpiCard, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";
import { ShieldCheck, ShieldAlert } from "lucide-react";

export default function Memory() {
  const { data, error } = useApi(() => api.memory(100));
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  const s = data.summary, ev = s.evaluation;
  return (
    <div className="content grid">
      <SyntheticNotice status={s.data_status} />
      {s.data_status === "SYNTHETIC" && <div className="callout">These are <b>replay</b> forecasts: recorded on a simulated clock before each outcome, then scored. They test the ledger, not the model's real-world skill.</div>}
      <div className="kpis">
        <KpiCard label="Forecasts recorded" value={String(s.predictions)} sub={`${s.replay_steps} rebalance dates`} />
        <KpiCard focus label="Ledger integrity" value={data.chain_verified ? "Verified" : `Broken @${data.first_bad_seq}`} sub="hash chain over every record" />
        <KpiCard label="Scored" value={`${ev.n_resolved}`} sub={`${ev.n_pending} pending`} />
      </div>
      <Panel title={<>{data.chain_verified ? <ShieldCheck size={16} color="var(--up)" /> : <ShieldAlert size={16} color="var(--down)" />} Ledger</>}
        right={<span className="faint mono">{s.model_version}</span>}>
        <table className="t">
          <thead><tr><th>Recorded</th><th>Ticker</th><th>Regime</th><th className="r">Forecast (excess)</th><th className="r">Actual</th><th className="r">Benchmark</th><th className="r">Excess</th><th>Due</th><th>Status</th></tr></thead>
          <tbody>{data.recent.map((r) => {
            const ex = r.actual_return != null && r.benchmark_return != null ? r.actual_return - r.benchmark_return : null;
            const hit = ex != null && r.forecast_return != null ? Math.sign(ex) === Math.sign(r.forecast_return) : null;
            return (
              <tr key={r.prediction_id}>
                <td className="mono faint">{r.created_at.slice(0, 16)}</td>
                <td><b>{r.ticker}</b></td>
                <td className="muted">{r.regime.replace("_", " ")}</td>
                <td className={`r num ${tone(r.forecast_return)}`}>{pct(r.forecast_return, 2)}</td>
                <td className={`r num ${tone(r.actual_return)}`}>{pct(r.actual_return, 2)}</td>
                <td className="r num muted">{pct(r.benchmark_return, 2)}</td>
                <td className={`r num ${tone(ex)}`}>{pct(ex, 2)} {hit == null ? "" : hit ? "✓" : "✗"}</td>
                <td className="mono faint">{r.target_time.slice(0, 10)}</td>
                <td><StatusBadge status={r.data_status} /></td>
              </tr>
            );
          })}</tbody>
        </table>
        <p className="faint" style={{ fontSize: 12 }}>Rows cannot be updated or deleted; outcomes are written once, after the due time. Showing the latest 100. Directional hit rate vs excess: {pctPlain(ev.directional_accuracy_vs_excess, 1)}.</p>
      </Panel>
    </div>
  );
}
