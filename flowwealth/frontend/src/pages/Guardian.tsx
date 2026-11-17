import { useState } from "react";
import { api, type RiskCheckResult } from "../lib/api";
import { useApi } from "../lib/useApi";
import { ErrorBox, Panel } from "../components/ui";

const HORIZONS = ["scalp", "intraday", "swing", "position", "long_term"];
const APPETITES = ["conservative", "moderate", "aggressive"];
const STATUSES = ["LIVE", "DELAYED", "HISTORICAL", "CACHED", "SYNTHETIC"];

export default function Guardian() {
  const limits = useApi(() => api.limits());
  const [f, setF] = useState({ horizon: "swing", appetite: "moderate", leverage: false, equity: 100000, peak: 100000, dayStart: 100000,
    ticker: "SYN0042", qty: 500, price: 50, stop: 47, dailyVol: 0.02, adv: 800000, status: "DELAYED", ageMin: 1 });
  const [res, setRes] = useState<RiskCheckResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.type === "number" ? Number(e.target.value) : e.target.value });
  const run = async (e: React.FormEvent) => {
    e.preventDefault(); setErr(null);
    try {
      setRes(await api.riskCheck({
        profile: { user_id: "local", horizon: f.horizon, appetite: f.appetite, capital: f.equity, leverage_permitted: f.leverage },
        order: { ticker: f.ticker, side: "buy", qty: f.qty, price: f.price, stop_price: f.stop, sector: "Technology",
          adv_shares: f.adv, daily_vol: f.dailyVol, data_status: f.status, horizon: f.horizon,
          data_timestamp: new Date(Date.now() - f.ageMin * 60000).toISOString() },
        equity: f.equity, peak_equity: f.peak, day_start_equity: f.dayStart, positions: [],
      }));
    } catch (x) { setErr((x as Error).message); }
  };
  const hard = limits.data?.hard_limits;
  return (
    <div className="content grid ember">
      <div className="grid g3">
        <Panel title="Pre-trade check" className="span2">
          <form onSubmit={run} className="grid g4" style={{ gap: 12 }}>
            <label className="field">Horizon<select value={f.horizon} onChange={set("horizon")}>{HORIZONS.map((h) => <option key={h}>{h}</option>)}</select></label>
            <label className="field">Risk appetite<select value={f.appetite} onChange={set("appetite")}>{APPETITES.map((h) => <option key={h}>{h}</option>)}</select></label>
            <label className="field">Equity<input type="number" value={f.equity} onChange={set("equity")} /></label>
            <label className="field">Peak equity<input type="number" value={f.peak} onChange={set("peak")} /></label>
            <label className="field">Start-of-day equity<input type="number" value={f.dayStart} onChange={set("dayStart")} /></label>
            <label className="field">Quantity<input type="number" value={f.qty} onChange={set("qty")} /></label>
            <label className="field">Price<input type="number" step="0.01" value={f.price} onChange={set("price")} /></label>
            <label className="field">Stop / invalidation<input type="number" step="0.01" value={f.stop} onChange={set("stop")} /></label>
            <label className="field">Daily volatility<input type="number" step="0.005" value={f.dailyVol} onChange={set("dailyVol")} /></label>
            <label className="field">Avg daily volume<input type="number" value={f.adv} onChange={set("adv")} /></label>
            <label className="field">Data status<select value={f.status} onChange={set("status")}>{STATUSES.map((h) => <option key={h}>{h}</option>)}</select></label>
            <label className="field">Data age (min)<input type="number" value={f.ageMin} onChange={set("ageMin")} /></label>
            <label className="field" style={{ alignSelf: "end" }}><span><input type="checkbox" checked={f.leverage} onChange={set("leverage")} /> leverage permitted</span></label>
            <div style={{ alignSelf: "end" }}><button className="btn" type="submit">Check order</button></div>
          </form>
          {err && <div style={{ marginTop: 12 }}><ErrorBox error={err} /></div>}
          {res && (
            <div style={{ marginTop: 18 }} aria-live="polite">
              <span className={`verdict ${res.verdict}`}>{res.verdict}</span>
              <span style={{ marginLeft: 12 }}>approved quantity <b className="num">{res.approved_qty}</b> of {f.qty}</span>
              <ul>{res.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              {"caps_qty" in res.checks && (
                <table className="t"><thead><tr><th>Limit</th><th className="r">Max quantity allowed</th></tr></thead>
                  <tbody>{Object.entries(res.checks.caps_qty as Record<string, number>).map(([k, v]) => (
                    <tr key={k}><td>{k.replace(/_/g, " ")}</td><td className="r num">{Math.floor(v).toLocaleString()}</td></tr>))}</tbody></table>
              )}
            </div>
          )}
        </Panel>
        <Panel title="Limits in force">
          {res ? (
            <table className="t"><thead><tr><th>Limit</th><th className="r">Profile</th><th className="r">Hard cap</th></tr></thead>
              <tbody>{Object.entries(res.effective_limits).map(([k, v]) => (
                <tr key={k}><td style={{ fontSize: 12 }}>{k.replace(/_/g, " ")}</td><td className="r num">{v}</td><td className="r num faint">{hard?.[k] ?? "—"}</td></tr>))}</tbody></table>
          ) : <p className="muted">Run a check to see the effective limits for this profile.</p>}
          <p className="faint" style={{ fontSize: 12 }}>
            The risk engine is independent of every AI component: it has no input for agent or judge opinions. Aggressive mode
            loosens limits only up to the hard caps; scalping requires LIVE data under 2 seconds old, and SYNTHETIC data is never actionable.
          </p>
        </Panel>
      </div>
    </div>
  );
}
