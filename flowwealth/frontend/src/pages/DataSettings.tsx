import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { int } from "../lib/format";
import { ErrorBox, Loading, Panel, StatusBadge } from "../components/ui";

export default function DataSettings() {
  const { data, error } = useApi(() => api.status());
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  const d = data.dataset;
  return (
    <div className="content grid">
      <div className="grid g2">
        <Panel title="Dataset" right={<StatusBadge status={data.data_status} />}>
          <table className="t"><tbody>
            <tr><td>Version</td><td className="mono">{d.version}</td></tr>
            <tr><td>Rows</td><td className="num">{int(d.rows)}</td></tr>
            <tr><td>Instruments</td><td className="num">{int(d.tickers)}</td></tr>
            <tr><td>Span</td><td>{d.start.slice(0, 10)} → {d.end.slice(0, 10)}</td></tr>
            <tr><td>Content hash</td><td className="mono">{d.content_sha256.slice(0, 16)}…</td></tr>
            <tr><td>Live feeds</td><td>{data.live_feeds.length ? data.live_feeds.join(", ") : "none connected"}</td></tr>
            <tr><td>Brokerage</td><td>{data.brokerage}</td></tr>
          </tbody></table>
        </Panel>
        <Panel title="Data quality">
          <table className="t"><tbody>{Object.entries(d.quality).map(([k, v]) => (
            <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="r num">{typeof v === "number" ? v.toLocaleString() : String(v)}</td></tr>
          ))}</tbody></table>
        </Panel>
      </div>
      <Panel title="Horizon readiness">
        <table className="t"><thead><tr><th>Horizon</th><th>Ready</th><th>Needs</th><th>Accepted data</th><th className="r">Max age</th></tr></thead>
          <tbody>{Object.entries(data.horizon_readiness).map(([h, r]) => (
            <tr key={h}><td>{h.replace("_", " ")}</td><td className={r.ready ? "up" : "down"}>{r.ready ? "yes" : "no"}</td>
              <td className="muted">{r.needs.join(", ")}</td><td className="muted">{r.status.join(", ")}</td><td className="r num">{r.max_age_s}s</td></tr>
          ))}</tbody></table>
        <p className="faint" style={{ fontSize: 12 }}>No horizon is marked ready while only synthetic data is loaded. Scalping stays disabled until a licensed tick/L2 feed is connected.</p>
      </Panel>
    </div>
  );
}
