import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { monogram, num, pct, pctPlain } from "../lib/format";
import { ErrorBox, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";

export default function Rankings() {
  const { data, error } = useApi(() => api.rankings());
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  const corr = Object.entries(data.feature_correlation_with_score).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
  const maxC = Math.max(...corr.map((c) => Math.abs(c[1])), 1e-9);
  return (
    <div className="content grid">
      <SyntheticNotice status={data.data_status} />
      <div className="grid g3">
        <Panel title={`Top 10 · ${data.horizon}`} className="span2" right={<StatusBadge status={data.data_status} />}>
          <table className="t">
            <thead><tr><th>#</th><th>Instrument</th><th>Sector</th><th className="r">Last</th><th className="r">Score</th><th className="r">20d return</th><th className="r">20d vol</th><th className="r">60d drawdown</th></tr></thead>
            <tbody>{data.items.map((it, i) => (
              <tr key={it.ticker}>
                <td className="faint">{i + 1}</td>
                <td><Link to={`/stock/${it.ticker}`} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="mono-badge" style={{ width: 26, height: 26, fontSize: 10 }}>{monogram(it.ticker)}</span><b>{it.ticker}</b>
                  <span className="faint">{it.exchange}</span></Link></td>
                <td className="muted">{it.sector}</td>
                <td className="r num">{num(it.adj_close)}</td>
                <td className="r num">{it.pred.toFixed(4)}</td>
                <td className="r num">{pct(Math.expm1(it.ret_20))}</td>
                <td className="r num">{pctPlain(it.vol_20 * Math.sqrt(252), 0)}</td>
                <td className="r num down">{pct(it.dd_60)}</td>
              </tr>
            ))}</tbody>
          </table>
          <p className="faint" style={{ fontSize: 12 }}>As of {data.as_of.slice(0, 16)} UTC. Only the swing horizon has a model; other horizons are not mixed into this list.</p>
        </Panel>
        <Panel title="Methodology">
          <p style={{ marginTop: 0, lineHeight: 1.55 }}>{data.methodology}</p>
          <p className="muted" style={{ fontSize: 12.5 }}>Target: {data.target}. Model: <span className="mono">{data.model_version}</span></p>
          <h2 style={{ marginTop: 18 }}>What moves the score</h2>
          <p className="faint" style={{ fontSize: 12, marginTop: -6 }}>Correlation of each input with today's score across the universe.</p>
          {corr.map(([k, v]) => (
            <div key={k} style={{ display: "grid", gridTemplateColumns: "120px 1fr 52px", gap: 8, alignItems: "center", margin: "5px 0", fontSize: 12 }}>
              <span className="mono">{k.replace(/_rk$/, "")}</span>
              <div className="hbar"><i style={{ width: `${(Math.abs(v) / maxC) * 100}%`, background: v < 0 ? "linear-gradient(90deg,#9e2f3a,var(--down))" : undefined }} /></div>
              <span className="num" style={{ textAlign: "right" }}>{v.toFixed(2)}</span>
            </div>
          ))}
        </Panel>
      </div>
      <p className="faint" style={{ fontSize: 12 }}>{data.disclaimer}</p>
    </div>
  );
}
