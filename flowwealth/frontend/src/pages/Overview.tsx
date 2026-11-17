import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { num, pct, pctPlain, tone } from "../lib/format";
import { ErrorBox, KpiCard, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";
import { AreaChart, Gauge, Sparkline } from "../components/charts";

export default function Overview() {
  const ov = useApi(() => api.overview());
  const crash = useApi(() => api.crash());
  const mem = useApi(() => api.memory(5));
  if (ov.error) return <div className="content"><ErrorBox error={ov.error} /></div>;
  if (!ov.data) return <div className="content"><Loading /></div>;
  const d = ov.data;
  const tiles = [d.composite, ...d.sectors.slice(0, 4)];
  const ev = mem.data?.summary.evaluation;
  return (
    <div className="content grid">
      <SyntheticNotice status={d.data_status} />
      <section className="panel strip" aria-label="Indices">
        {tiles.map((t) => (
          <div className="tile" key={t.name}>
            <div className="label">{t.name}</div>
            <div className="val num">{num(t.value)}</div>
            <div className={`num ${tone(t.change_1d)}`} style={{ fontSize: 12 }}>{t.change_1d >= 0 ? "↗" : "↘"} {pct(t.change_1d)}</div>
          </div>
        ))}
      </section>

      <div className="kpis">
        <KpiCard label="Breadth" value={pctPlain(d.breadth_up, 0)} sub="names up today" spark={d.composite.spark} />
        <KpiCard focus label="Crash-risk level" value={crash.data?.current.level ?? "—"}
          sub={crash.data ? `score ${crash.data.current.score}/5 · regime ${crash.data.current.regime}` : ""} />
        <KpiCard label="Forecasts scored" value={ev ? String(ev.n_resolved) : "—"}
          sub={ev ? `directional ${pctPlain(ev.directional_accuracy_vs_excess, 1)} vs excess` : ""} />
      </div>

      <div className="grid g3">
        <Panel title="Market breadth" right={<StatusBadge status={d.data_status} />}>
          <div className="gauge-wrap"><Gauge value={d.breadth_up} label="Breadth" sub={`${pctPlain(d.breadth_up, 0)} advancing`} /></div>
          <p className="faint" style={{ fontSize: 12, margin: 0 }}>Share of universe names with a positive return in the latest session.</p>
        </Panel>
        <Panel title="FW Composite (equal-weight)" className="span2" right={<span className="faint">last 30 sessions</span>}>
          <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
            <span className="num" style={{ fontSize: 30, fontWeight: 600 }}>{num(d.composite.value)}</span>
            <span className={`num ${tone(d.composite.change_1d)}`}>{pct(d.composite.change_1d)}</span>
          </div>
          <AreaChart values={d.composite.spark} height={180} />
        </Panel>
      </div>

      <div className="grid g3">
        <Panel title="Sector strength" right={<span className="faint">index · 1d</span>}>
          {d.sectors.map((s) => {
            const w = Math.max(4, Math.min(100, 50 + s.change_1d * 2000));
            return (
              <div key={s.name} style={{ display: "grid", gridTemplateColumns: "110px 1fr 64px", gap: 10, alignItems: "center", margin: "7px 0" }}>
                <span style={{ fontSize: 12.5 }}>{s.name}</span>
                <div className="hbar" aria-hidden="true"><i style={{ width: `${w}%`, background: s.change_1d < 0 ? "linear-gradient(90deg,#9e2f3a,var(--down))" : undefined }} /></div>
                <span className={`num r ${tone(s.change_1d)}`} style={{ fontSize: 12, textAlign: "right" }}>{pct(s.change_1d)}</span>
              </div>
            );
          })}
        </Panel>
        <Panel title="Top movers" className="span2" right={<Link to="/markets" className="faint">All markets →</Link>}>
          <table className="t">
            <thead><tr><th>Instrument</th><th>Sector</th><th className="r">Close</th><th className="r">1d</th></tr></thead>
            <tbody>
              {[...d.gainers, ...d.losers].map((m) => (
                <tr key={m.ticker}>
                  <td><Link to={`/stock/${m.ticker}`}><b>{m.ticker}</b></Link></td>
                  <td className="muted">{m.sector}</td>
                  <td className="r num">{num(m.close)}</td>
                  <td className={`r num ${tone(m.change)}`}>{pct(m.change)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      </div>

      <Panel title="Country composites" right={<span className="faint">equal-weight · last 30 sessions</span>}>
        <div className="grid g5">
          {d.countries.map((c) => (
            <div key={c.name} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <b style={{ width: 28 }}>{c.name}</b>
              <Sparkline values={c.spark} />
              <span className={`num ${tone(c.change_1d)}`} style={{ fontSize: 12 }}>{pct(c.change_1d)}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
