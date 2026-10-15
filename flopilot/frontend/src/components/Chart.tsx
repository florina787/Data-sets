import { compactNumber, formatNumber, niceTicks } from "../lib/format";
import type { ChartSpec, Source } from "../lib/types";

const COLORS = ["#107C41", "#0B4F35", "#6DB33F", "#2563EB", "#B45309", "#7C3AED", "#0E7490", "#BE185D"];
const W = 340;
const H = 214;
const M = { top: 10, right: 10, bottom: 62, left: 48 };

export function Chart({ spec, onSource }: { spec: ChartSpec; onSource?: (s: Source) => void }) {
  return (
    <figure className="chart" aria-label={spec.title}>
      <h5>{spec.title}</h5>
      <div className="sub">
        {spec.y_label}
        {spec.web_only && " · shown in FloPilot only (not embedded in the workbook)"}
      </div>
      {spec.type === "table" ? <ChartTable spec={spec} /> : spec.type === "line" ? <LineChart spec={spec} /> : spec.type === "scatter" ? <Scatter spec={spec} /> : <Bars spec={spec} />}
      {spec.series.length > 1 && (
        <div className="legend">
          {spec.series.map((s, i) => <span key={s.name}><i style={{ background: COLORS[i % COLORS.length] }} />{s.name}</span>)}
        </div>
      )}
      {spec.notes.length > 0 && <div className="sub" style={{ marginTop: 4 }}>{spec.notes.join(" ")}</div>}
      {spec.sources.length > 0 && onSource && (
        <div className="meta-row">
          <span className="meta-label">Data</span>
          {spec.sources.map((s) => <button key={s.id} className="chip link" onClick={() => onSource(s)}>{s.label}</button>)}
        </div>
      )}
      <figcaption className="sr-only">{describe(spec)}</figcaption>
    </figure>
  );
}

function describe(spec: ChartSpec): string {
  return spec.series.map((s) => `${s.name}: ` + s.points.map((p) => `${p.x} ${p.y ?? "no data"}`).join(", ")).join("; ");
}

function scaleY(values: number[]) {
  const min = Math.min(0, ...values);
  const max = Math.max(0, ...values);
  const ticks = niceTicks(min, max === min ? min + 1 : max, 4);
  const lo = ticks[0];
  const hi = ticks[ticks.length - 1];
  const y = (v: number) => M.top + (H - M.top - M.bottom) * (1 - (v - lo) / (hi - lo || 1));
  return { y, ticks };
}

function Axes({ ticks, y, unit }: { ticks: number[]; y: (v: number) => number; unit: string | null }) {
  return (
    <g>
      {ticks.map((t) => (
        <g key={t}>
          <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="#E5E7EB" />
          <text x={M.left - 4} y={y(t) + 3} textAnchor="end">{unit === "%" ? `${Math.round(t * 100)}%` : compactNumber(t)}</text>
        </g>
      ))}
    </g>
  );
}

function Bars({ spec }: { spec: ChartSpec }) {
  const cats = spec.series[0].points.map((p) => String(p.x));
  const values = spec.series.flatMap((s) => s.points.map((p) => p.y ?? 0));
  const { y, ticks } = scaleY(values);
  const band = (W - M.left - M.right) / Math.max(cats.length, 1);
  const barW = Math.max(3, (band * 0.7) / spec.series.length);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={spec.title}>
      <Axes ticks={ticks} y={y} unit={spec.unit} />
      {spec.series.map((s, si) =>
        s.points.map((p, i) => {
          const v = p.y ?? 0;
          const x = M.left + i * band + band * 0.15 + si * barW;
          return (
            <rect key={`${si}-${i}`} x={x} width={barW - 1} y={Math.min(y(v), y(0))} height={Math.max(1, Math.abs(y(v) - y(0)))}
              fill={v < 0 ? "#B42318" : COLORS[si % COLORS.length]} rx="1.5">
              <title>{`${p.x}: ${p.y === null ? "no data" : formatNumber(v, spec.unit)}`}</title>
            </rect>
          );
        }),
      )}
      {cats.map((c, i) => (
        <text key={c + i} x={M.left + i * band + band / 2} y={H - M.bottom + 12} textAnchor="end" transform={`rotate(-30 ${M.left + i * band + band / 2} ${H - M.bottom + 12})`}>
          {c.length > 14 ? c.slice(0, 13) + "…" : c}
        </text>
      ))}
      <text x={W / 2} y={H - 2} textAnchor="middle">{spec.x_label}</text>
    </svg>
  );
}

function LineChart({ spec }: { spec: ChartSpec }) {
  const cats = spec.series[0].points.map((p) => String(p.x));
  const values = spec.series.flatMap((s) => s.points.filter((p) => p.y !== null).map((p) => p.y as number));
  const { y, ticks } = scaleY(values);
  const step = (W - M.left - M.right) / Math.max(cats.length - 1, 1);
  const x = (i: number) => M.left + i * step;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={spec.title}>
      <Axes ticks={ticks} y={y} unit={spec.unit} />
      {spec.series.map((s, si) => {
        // Gaps (null) break the line instead of being drawn as zero.
        const segments: string[] = [];
        let current = "";
        s.points.forEach((p, i) => {
          if (p.y === null) {
            if (current) segments.push(current);
            current = "";
          } else current += `${current ? "L" : "M"}${x(i)},${y(p.y)}`;
        });
        if (current) segments.push(current);
        return (
          <g key={s.name}>
            {segments.map((d, k) => <path key={k} d={d} fill="none" stroke={COLORS[si % COLORS.length]} strokeWidth="2.2" />)}
            {s.points.map((p, i) => p.y !== null && (
              <circle key={i} cx={x(i)} cy={y(p.y)} r="3" fill={COLORS[si % COLORS.length]}><title>{`${p.x}: ${formatNumber(p.y, spec.unit)}`}</title></circle>
            ))}
          </g>
        );
      })}
      {cats.map((c, i) => <text key={c} x={x(i)} y={H - M.bottom + 14} textAnchor="middle">{c}</text>)}
      <text x={W / 2} y={H - 4} textAnchor="middle">{spec.x_label}</text>
    </svg>
  );
}

function Scatter({ spec }: { spec: ChartSpec }) {
  const pts = spec.series[0].points.filter((p) => typeof p.x === "number" && p.y !== null) as { x: number; y: number }[];
  const { y, ticks } = scaleY(pts.map((p) => p.y));
  const xs = pts.map((p) => p.x);
  const xt = niceTicks(Math.min(...xs), Math.max(...xs), 4);
  const x = (v: number) => M.left + (W - M.left - M.right) * ((v - xt[0]) / (xt[xt.length - 1] - xt[0] || 1));
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={spec.title}>
      <Axes ticks={ticks} y={y} unit={null} />
      {xt.map((t) => <text key={t} x={x(t)} y={H - M.bottom + 14} textAnchor="middle">{compactNumber(t)}</text>)}
      {pts.map((p, i) => <circle key={i} cx={x(p.x)} cy={y(p.y)} r="2.6" fill="#107C41" opacity="0.7" />)}
      <text x={W / 2} y={H - 4} textAnchor="middle">{spec.x_label}</text>
    </svg>
  );
}

function ChartTable({ spec }: { spec: ChartSpec }) {
  return (
    <table className="result-table">
      <thead><tr><th>{spec.x_label}</th><th>{spec.y_label}</th></tr></thead>
      <tbody>{spec.series[0].points.map((p, i) => <tr key={i}><td>{p.x}</td><td className="num">{p.y === null ? "—" : formatNumber(p.y, spec.unit)}</td></tr>)}</tbody>
    </table>
  );
}
