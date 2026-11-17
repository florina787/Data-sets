import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { monogram, num, pct, tone } from "../lib/format";
import { StatusBadge } from "../components/ui";
import SymbolSearch from "../components/SymbolSearch";

export default function Home() {
  const { data } = useApi(() => api.overview());
  const movers = data ? [...data.gainers.slice(0, 3), ...data.losers.slice(0, 2)] : [];
  return (
    <div>
      <section className="hero">
        <div className="eyebrow">Evidence-first market research</div>
        <h1>Every forecast recorded.<br /><em>Every model earns its place.</em></h1>
        <p>
          FLOW WEALTH logs each prediction before its outcome is known, scores it afterwards, and only promotes models that
          beat simple baselines after realistic costs. Independent risk limits apply to every profile.
        </p>
        <SymbolSearch />
        {data && <div style={{ marginTop: 14 }}><StatusBadge status={data.data_status} /> <span className="faint">as of {data.as_of.slice(0, 16)} UTC</span></div>}
        <div className="cards" aria-label="Today's largest moves">
          {movers.map((m, i) => (
            <Link to={`/stock/${m.ticker}`} key={m.ticker} className={`tcard ${i === 3 ? "hl" : ""}`}>
              <div className="top">
                <span className="mono-badge">{monogram(m.ticker)}</span>
                <div><b>{m.ticker}</b><div className="faint" style={{ fontSize: 12 }}>{m.sector}</div></div>
              </div>
              <div className="px num">{num(m.close)}</div>
              <div className={`num ${tone(m.change)}`} style={{ fontSize: 12 }}>{m.change >= 0 ? "▲" : "▼"} {pct(m.change)} · 1 session</div>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
