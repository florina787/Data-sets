import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { pctPlain } from "../lib/format";
import { ErrorBox, KpiCard, Loading, Panel, SyntheticNotice } from "../components/ui";

export default function Models() {
  const { data, error } = useApi(() => api.memory(1));
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  const s = data.summary, ev = s.evaluation;
  const drift = Object.entries(s.feature_drift_psi_dev_vs_holdout).sort((a, b) => b[1] - a[1]);
  const ic = ev.rank_ic_vs_excess;
  return (
    <div className="content grid">
      <SyntheticNotice status={s.data_status} />
      <div className="kpis">
        <KpiCard label="Directional vs excess" value={pctPlain(ev.directional_accuracy_vs_excess, 1)} sub="coin flip = 50%" />
        <KpiCard focus label="Rank IC vs excess" change={ic != null ? (ic >= 0 ? "+" : "-") + Math.abs(ic).toFixed(3) : undefined}
          value={ic != null ? ic.toFixed(3) : "—"} sub="on scored forecasts" />
        <KpiCard label="Mean abs. error" value={ev.mae != null ? pctPlain(ev.mae, 2) : "—"} sub="forecast vs actual" />
      </div>
      <div className="grid g2">
        <Panel title="Outcome by regime">
          <table className="t"><thead><tr><th>Regime at forecast</th><th className="r">Forecasts</th><th className="r">Direction correct</th></tr></thead>
            <tbody>{(ev.by_regime ?? []).map((r) => (
              <tr key={r.regime}><td>{r.regime.replace("_", " ")}</td><td className="r num">{r.count}</td>
                <td className="r"><div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end" }}>
                  <div className="hbar" style={{ width: 100 }}><i style={{ width: `${r.mean * 100}%` }} /></div>
                  <span className="num">{pctPlain(r.mean, 0)}</span></div></td></tr>
            ))}</tbody></table>
          <p className="faint" style={{ fontSize: 12 }}>Small samples per regime: treat differences as unconfirmed.</p>
        </Panel>
        <Panel title="Feature drift (PSI, development vs holdout)">
          <table className="t"><thead><tr><th>Feature</th><th className="r">PSI</th><th>Reading</th></tr></thead>
            <tbody>{drift.map(([k, v]) => (
              <tr key={k}><td className="mono">{k}</td><td className="r num">{v.toFixed(3)}</td>
                <td className={v > 0.25 ? "down" : v > 0.1 ? "" : "muted"}>{v > 0.25 ? "significant shift" : v > 0.1 ? "moderate" : "stable"}</td></tr>
            ))}</tbody></table>
        </Panel>
      </div>
      <Panel title="Champion–challenger">
        <p style={{ marginTop: 0 }}>No model is in production. Promotion requires, on the untouched holdout: IC t-stat ≥ 2, consistently positive walk-forward IC,
          positive Sharpe <b>after costs</b>, beating every simple baseline after costs, drawdown better than −25%, and a named human approver. Rollback restores the previous champion.</p>
        <p className="muted" style={{ marginBottom: 0 }}>Current candidate <span className="mono">{s.model_version}</span>: not eligible (net Sharpe negative in the Strategy Research Lab).</p>
      </Panel>
    </div>
  );
}
