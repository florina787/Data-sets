import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { num, pct, pctPlain, tone } from "../lib/format";
import { ErrorBox, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";
import { SegmentedMeter, Sparkline } from "../components/charts";
import { MessageCircle } from "lucide-react";

const LEVEL_COLOR: Record<string, string> = { Normal: "#3fd68b", Elevated: "#ffb547", High: "#ff7a2f", Critical: "#ff4d3d" };
const INPUTS: { key: string; label: string; rule: string; fmt: (v: number) => string }[] = [
  { key: "vol_pctile", label: "Volatility percentile (1y)", rule: "> 80% adds 1, > 95% adds 2", fmt: (v) => pctPlain(v, 0) },
  { key: "drawdown", label: "Drawdown from 1y peak", rule: "< −10% adds 1", fmt: (v) => pct(v, 1) },
  { key: "trend_200", label: "Index vs 200-day mean", rule: "< 0 adds 1", fmt: (v) => pct(v, 1) },
  { key: "breadth_above_ma50", label: "Breadth above 50-day mean", rule: "< 30% adds 1", fmt: (v) => pctPlain(v, 0) },
  { key: "vol_20", label: "Realized volatility (20d, ann.)", rule: "context only", fmt: (v) => pctPlain(v, 1) },
  { key: "dispersion", label: "Cross-sectional dispersion", rule: "context only", fmt: (v) => pctPlain(v, 2) },
];

function volTag(spark: number[]) {
  const r = spark.slice(1).map((v, i) => Math.log(v / spark[i]));
  const m = r.reduce((a, b) => a + b, 0) / Math.max(r.length, 1);
  const sd = Math.sqrt(r.reduce((a, b) => a + (b - m) ** 2, 0) / Math.max(r.length - 1, 1)) * Math.sqrt(252);
  return { sd, tag: sd > 0.3 ? "High volatility" : sd > 0.15 ? "Medium volatility" : "Low volatility" };
}

export default function CrashRisk() {
  const { data, error } = useApi(() => api.crash());
  const ov = useApi(() => api.overview());
  if (error) return <div className="content ember"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content ember"><Loading /></div>;
  const lvl = data.current.level;
  return (
    <div className="content grid ember">
      <SyntheticNotice status={data.data_status} />
      <div className="grid g3">
        <Panel title="Market crash-risk condition" className="span2" right={<StatusBadge status={data.data_status} />}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 14 }}>
            <span style={{ fontSize: 40, fontWeight: 600, color: LEVEL_COLOR[lvl] }}>{lvl}</span>
            <span className="muted">score {data.current.score} / 5 · regime <b>{data.current.regime.replace("_", " ")}</b> · {data.as_of.slice(0, 10)}</span>
          </div>
          <SegmentedMeter on={Math.round((data.current.score / 5) * 40)} label={`Crash-risk score ${data.current.score} of 5`} />
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginTop: 6 }} className="faint">
            <span>Normal</span><span>Elevated</span><span>High</span><span>Critical</span>
          </div>
          <p className="faint" style={{ fontSize: 12, marginBottom: 0 }}>
            An estimated risk <i>condition</i> from transparent indicators, not a crash prediction. Its track record is shown on the right.
          </p>
        </Panel>
        <Panel title="How often has this alarm been right?">
          {data.evaluation.map((e) => (
            <div key={e.alarm_level} style={{ marginBottom: 12 }}>
              <div style={{ fontWeight: 600 }}>Alarm at “{e.alarm_level}” or above</div>
              <div className="muted" style={{ fontSize: 12.5, lineHeight: 1.6 }}>
                Precision <b className="num">{pctPlain(e.precision, 0)}</b> · recall <b className="num">{pctPlain(e.recall, 0)}</b><br />
                {e.false_alarm_days} false-alarm days · {e.missed_event_days} missed event days<br />
                base rate {pctPlain(e.event_days / e.days, 1)} of {e.days} days
              </div>
            </div>
          ))}
          <p className="faint" style={{ fontSize: 11.5, margin: 0 }}>Event: {data.evaluation[0]?.definition}. Thresholds were fixed before evaluation, not tuned on it.</p>
        </Panel>
      </div>

      <Panel title="Inputs behind the level">
        <table className="t">
          <thead><tr><th>Indicator</th><th className="r">Current</th><th>Rule</th></tr></thead>
          <tbody>{INPUTS.map((i) => {
            const v = data.inputs[i.key];
            return <tr key={i.key}><td>{i.label}</td><td className="r num">{v == null ? "—" : i.fmt(v)}</td><td className="muted">{i.rule}</td></tr>;
          })}</tbody>
        </table>
      </Panel>

      <Panel title="Level history · last 260 sessions">
        <div style={{ display: "flex", gap: 1, height: 26 }} role="img" aria-label="Daily crash-risk level history">
          {data.history.map((h) => <i key={h.date} title={`${h.date}: ${h.level}`} style={{ flex: 1, background: LEVEL_COLOR[h.level], opacity: 0.85, borderRadius: 1 }} />)}
        </div>
      </Panel>

      {ov.data && (
        <div className="grid g3">
          {ov.data.sectors.slice(0, 6).map((s) => {
            const v = volTag(s.spark);
            return (
              <Panel key={s.name} title={<>{s.name}<span className="vtag">{v.tag}</span></>}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div><div className="num" style={{ fontSize: 22 }}>{num(s.value)}</div>
                    <div className={`num ${tone(s.change_1d)}`} style={{ fontSize: 12 }}>{pct(s.change_1d)} 1d</div></div>
                  <Sparkline values={s.spark} width={120} height={36} />
                </div>
                <div style={{ marginTop: 12 }}><SegmentedMeter on={Math.min(30, Math.round(v.sd / 0.5 * 30))} segments={30} label={`${s.name} 30-session volatility ${pctPlain(v.sd, 0)}`} /></div>
                <div className="faint" style={{ fontSize: 11, marginTop: 4 }}>30-session realized vol {pctPlain(v.sd, 0)} (ann.)</div>
              </Panel>
            );
          })}
        </div>
      )}

      <div className="ask" aria-disabled="true">
        <MessageCircle size={18} color="var(--ember1)" />
        <input disabled placeholder="Risk assistant (planned): will answer only from the indicators on this page" aria-label="Risk assistant, not yet available" />
      </div>
    </div>
  );
}
