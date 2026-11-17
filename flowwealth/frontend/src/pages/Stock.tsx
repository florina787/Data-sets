import { useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Star } from "lucide-react";
import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { monogram, num, pct, tone } from "../lib/format";
import { getWatchlist, toggleWatch } from "../lib/watchlist";
import { ErrorBox, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";
import { DotField } from "../components/charts";

const RANGES = ["1W", "1M", "3M", "1Y", "2Y", "MAX"] as const;

export default function Stock() {
  const { ticker = "" } = useParams();
  const [range, setRange] = useState<(typeof RANGES)[number]>("1Y");
  const [watch, setWatch] = useState(getWatchlist());
  const { data, error } = useApi(() => api.series(ticker, range), [ticker, range]);
  const rk = useApi(() => api.rankings());
  const stats = useMemo(() => {
    if (!data || data.points.length < 2) return null;
    const p = data.points.map((x) => x.c);
    const last = p[p.length - 1];
    return { last, d1: last / p[p.length - 2] - 1, w1: p.length > 5 ? last / p[p.length - 6] - 1 : null, period: last / p[0] - 1, values: p };
  }, [data]);
  const rankPos = rk.data?.items.findIndex((i) => i.ticker === ticker.toUpperCase()) ?? -1;
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  return (
    <div className="content grid">
      <SyntheticNotice status={data?.data_status} />
      <Panel>
        <div className="chart-head">
          <span className="mono-badge" style={{ width: 44, height: 44 }}>{monogram(ticker)}</span>
          <div>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{ticker.toUpperCase()}</div>
            <div className="muted">{data ? `${data.sector} · ${data.exchange}` : "…"}{data?.delisted && <span className="down"> · delisted {data.delisted}</span>}</div>
          </div>
          <button className="chips" style={{ marginLeft: "auto", padding: "6px 12px" }} aria-pressed={watch.includes(ticker.toUpperCase())}
            onClick={() => setWatch(toggleWatch(ticker.toUpperCase()))}>
            <Star size={14} fill={watch.includes(ticker.toUpperCase()) ? "currentColor" : "none"} />&nbsp;{watch.includes(ticker.toUpperCase()) ? "Watching" : "Add to watchlist"}
          </button>
          {data && <StatusBadge status={data.data_status} />}
        </div>
        <div className="chips" role="group" aria-label="Range">
          {RANGES.map((r) => <button key={r} aria-pressed={r === range} onClick={() => setRange(r)}>{r}</button>)}
        </div>
        {stats ? (
          <>
            <div className="chart-head" style={{ marginTop: 18 }}>
              <div><div className="px num">{num(stats.last)}</div><div className="faint">adjusted close</div></div>
              <div><div className={`num ${tone(stats.d1)}`} style={{ fontSize: 20 }}>{pct(stats.d1)}</div><div className="faint">1 session</div></div>
              <div><div className={`num ${tone(stats.w1)}`} style={{ fontSize: 20 }}>{pct(stats.w1)}</div><div className="faint">5 sessions</div></div>
              <div><div className={`num ${tone(stats.period)}`} style={{ fontSize: 20 }}>{pct(stats.period)}</div><div className="faint">{range}</div></div>
            </div>
            <DotField values={stats.values} height={320} label={`${ticker} adjusted close, ${range}`} />
          </>
        ) : <Loading />}
      </Panel>
      <div className="grid g2">
        <Panel title="Model view" right={rk.data && <span className="faint">{rk.data.model_version}</span>}>
          {rankPos >= 0 ? (
            <p>Ranked <b>#{rankPos + 1}</b> of the top-10 swing list ({rk.data!.horizon}) as of {rk.data!.as_of.slice(0, 10)}.</p>
          ) : <p className="muted">Not in the current top-10 swing list.</p>}
          <p className="faint" style={{ fontSize: 12 }}>Scores are uncalibrated rankings, not return promises. See Model Performance for how this model's past forecasts turned out.</p>
        </Panel>
        <Panel title="Bull vs bear evidence">
          <p className="muted" style={{ margin: 0 }}>Not implemented yet. The debate agents are planned to cite point-in-time evidence only; until then no thesis is shown rather than an unsupported one.</p>
        </Panel>
      </div>
    </div>
  );
}
