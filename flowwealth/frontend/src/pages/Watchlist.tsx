import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Series } from "../lib/api";
import { useApi } from "../lib/useApi";
import { monogram, num, pct } from "../lib/format";
import { getWatchlist, setWatchlist } from "../lib/watchlist";
import { Panel, SyntheticNotice } from "../components/ui";

const FLAGS: Record<string, string> = { US: "🇺🇸", CA: "🇨🇦", GB: "🇬🇧", DE: "🇩🇪", FR: "🇫🇷", JP: "🇯🇵", HK: "🇭🇰", IN: "🇮🇳", AU: "🇦🇺", BR: "🇧🇷" };

export default function Watchlist() {
  const ov = useApi(() => api.overview());
  const [list, setList] = useState<string[]>(getWatchlist());
  const [rows, setRows] = useState<Record<string, Series>>({});
  useEffect(() => {
    if (!list.length && ov.data) { const seed = ov.data.gainers.slice(0, 3).map((g) => g.ticker); setWatchlist(seed); setList(seed); }
  }, [ov.data, list.length]);
  useEffect(() => {
    list.forEach((t) => api.series(t, "1W").then((s) => setRows((r) => ({ ...r, [t]: s }))).catch(() => undefined));
  }, [list]);
  const [adding, setAdding] = useState("");
  const add = (e: React.FormEvent) => {
    e.preventDefault();
    const t = adding.trim().toUpperCase();
    if (!t) return;
    const next = [...new Set([...list, t])]; setWatchlist(next); setList(next); setAdding("");
  };
  return (
    <div className="content grid">
      <SyntheticNotice status={ov.data?.data_status} />
      <div className="grid g2">
        <div className="guide-wrap">
          <div className="watch">
            {list.map((t) => {
              const s = rows[t]; const p = s?.points ?? [];
              const last = p[p.length - 1]?.c, prev = p[p.length - 2]?.c;
              const ch = last && prev ? last / prev - 1 : null;
              return (
                <Link to={`/stock/${t}`} className="row" key={t}>
                  <span className="mono-badge" style={{ color: "#16181f", background: "#eef0f6" }}>{monogram(t)}</span>
                  <div><div className="tk">${t}</div><div className="nm">{s ? `${s.sector} · ${s.exchange}` : "…"}</div></div>
                  <div className="px"><div className="num">{last ? num(last) : "—"}</div>
                    <div className={`num ${ch == null ? "" : ch >= 0 ? "up" : "down"}`} style={{ fontSize: 13 }}>{ch == null ? "" : `${ch >= 0 ? "▲" : "▼"} ${pct(ch)}`}</div></div>
                </Link>
              );
            })}
            <div className="chipsrow" aria-label="Country composites">
              {ov.data?.countries.map((c) => (
                <span className="ichip" key={c.name}><span aria-hidden="true">{FLAGS[c.name] ?? "🏳"}</span><b>{c.name}</b>
                  <span className={c.change_1d >= 0 ? "up" : "down"}>{c.change_1d >= 0 ? "▲" : "▼"}{pct(c.change_1d, 1).replace(/^[+-]/, "")}</span></span>
              ))}
            </div>
            <form onSubmit={add} style={{ display: "flex", gap: 8, borderTop: "1px solid #eceef3", paddingTop: 8 }}>
              <input value={adding} onChange={(e) => setAdding(e.target.value)} placeholder="Ticker, e.g. SYN0042" aria-label="Ticker to add"
                style={{ flex: 1, border: 0, outline: 0, background: "none", color: "#16181f", font: "inherit" }} maxLength={12} />
              <button className="add" type="submit" style={{ width: "auto", borderTop: 0 }}>Add to watchlist +</button>
            </form>
          </div>
        </div>
        <Panel title="Getting started">
          <ol style={{ lineHeight: 1.8, paddingLeft: 18, margin: 0 }}>
            <li><b>Check the data badge.</b> Every number says whether it is LIVE, DELAYED, HISTORICAL, SYNTHETIC or HYPOTHETICAL.</li>
            <li><b>Pick a horizon and a risk appetite</b> separately: trading fast does not mean taking more risk.</li>
            <li><b>Read the evidence, not the rank.</b> Rankings show the method and what drives each score.</li>
            <li><b>Look at the track record.</b> Prediction Memory shows how past forecasts actually turned out.</li>
            <li><b>Run orders past the Risk Guardian</b> before acting; it applies limits that no profile can switch off.</li>
            <li><b>Practise with paper trading</b> (planned). There is no live brokerage connection.</li>
          </ol>
        </Panel>
      </div>
    </div>
  );
}
