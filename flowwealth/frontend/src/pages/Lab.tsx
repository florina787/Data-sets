import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { int, pct, pctPlain } from "../lib/format";
import { ErrorBox, Loading, Panel, StatusBadge } from "../components/ui";

const f2 = (x: number | null | undefined, d = 2) => (x == null ? "—" : x.toFixed(d));

export default function Lab() {
  const { data, error } = useApi(() => api.experiments());
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  if (!data.experiments.length) return <div className="content"><Panel>No experiments yet. Run <span className="mono">python -m flowwealth.research.experiment</span>.</Panel></div>;
  return (
    <div className="content grid">
      {data.experiments.map((e) => (
        <div key={e.experiment} className="grid">
          {e.caveat && <div className="callout">{e.caveat}</div>}
          <Panel title={<>{e.experiment} {e.data_status?.map((s) => <StatusBadge key={s} status={s} />)}</>}
            right={<span className="faint">{int(e.rows_modelled)} rows · {e.horizon_bars}-bar horizon</span>}>
            <div className="grid g3" style={{ marginBottom: 14 }}>
              {Object.entries(e.split ?? {}).map(([k, v]) => (
                <div key={k} className="kpi" style={{ padding: 12 }}>
                  <span className="pill">{k}</span>
                  <div className="num" style={{ marginTop: 8 }}>{int(v.rows)} rows</div>
                  <div className="faint" style={{ fontSize: 12 }}>{v.start.slice(0, 10)} → {v.end.slice(0, 10)}</div>
                </div>
              ))}
            </div>
            <h2>Holdout (scored once) — gross vs net of costs</h2>
            <table className="t">
              <thead><tr><th>Model</th><th className="r">Rank IC</th><th className="r">IC t-stat</th><th className="r">Sharpe gross</th>
                <th className="r">Sharpe net</th><th className="r">Net max DD</th><th className="r">Net total</th><th className="r">Avg turnover</th></tr></thead>
              <tbody>{Object.entries(e.holdout ?? {}).map(([m, h]) => {
                const bt = h.backtest_long_short;
                const failsCost = bt && (bt.gross.sharpe ?? 0) > 0 && (bt.net.sharpe ?? 0) <= 0;
                return (
                  <tr key={m}>
                    <td><b>{m}</b> {["zero", "momentum", "reversal_5d"].includes(m) && <span className="faint">baseline</span>}</td>
                    <td className="r num">{f2(h.ic.ic_mean, 4)}</td>
                    <td className="r num">{f2(h.ic.ic_t)}</td>
                    <td className="r num">{f2(bt?.gross.sharpe)}</td>
                    <td className={`r num ${!bt ? "" : (bt.net.sharpe ?? 0) < 0 ? "down" : "up"}`}>{f2(bt?.net.sharpe)}{failsCost && " ⚠"}</td>
                    <td className={`r num ${bt ? "down" : ""}`}>{bt ? pct(bt.net.max_drawdown, 1) : "—"}</td>
                    <td className="r num">{bt ? pct(bt.net.total_return, 1) : "—"}</td>
                    <td className="r num">{bt ? pctPlain(bt.avg_turnover, 0) : "—"}</td>
                  </tr>
                );
              })}</tbody>
            </table>
            <p className="faint" style={{ fontSize: 12 }}>⚠ positive before costs, negative after: would not be promoted. Long/short deciles, rebalanced every horizon, with commission, spread, slippage, square-root impact, borrow and a 5%-of-ADV liquidity cap.</p>
            <h2 style={{ marginTop: 18 }}>Walk-forward model selection (inside train + validation)</h2>
            <table className="t">
              <thead><tr><th>Model</th><th className="r">Mean IC</th><th className="r">Worst fold IC</th><th className="r">Folds positive</th></tr></thead>
              <tbody>{e.walk_forward_summary.map((w) => (
                <tr key={w.model}><td>{w.model}</td><td className="r num">{f2(w.ic_mean, 4)}</td><td className="r num">{f2(w.ic_min, 4)}</td><td className="r num">{w.folds_positive}</td></tr>
              ))}</tbody>
            </table>
          </Panel>
        </div>
      ))}
    </div>
  );
}
