import { ReactNode, useState } from "react";

// Small inline SVG charts. Single-series charts carry no legend (the title names the
// series); every chart has a hover tooltip and a table view, and text uses text
// colours rather than the series colour. Colours: series #2f7d4f; diverging
// gain #2f7d4f / loss #9b2c2c (validated pair, secondary-encoded by sign labels and
// direction); status colours always come with a text label.

const INK = "#1a2d52";
const MUTED = "#3d5a8f";
const GRID = "#e6dbc2";
const SERIES = "#2f7d4f";
const LOSS = "#9b2c2c";

export function ChartCard({ title, subtitle, table, children }: { title: string; subtitle?: string; table: ReactNode; children: ReactNode }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className="card">
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
        <figcaption>
          <div className="font-semibold text-navy-900">{title}</div>
          {subtitle && <div className="text-xs text-navy-600">{subtitle}</div>}
        </figcaption>
        <button className="btn-ghost text-xs" onClick={() => setShowTable((v) => !v)} aria-pressed={showTable}>
          {showTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {showTable ? <div className="max-h-72 overflow-auto">{table}</div> : children}
    </figure>
  );
}

type Point = { label: string; value: number };

export function LineChart({ points, format, ariaLabel }: { points: Point[]; format: (v: number) => string; ariaLabel: string }) {
  const [hover, setHover] = useState<number | null>(null);
  const w = 640, h = 200, pl = 56, pr = 16, pt = 12, pb = 28;
  if (points.length === 0) return <p className="text-sm text-navy-600">No data.</p>;
  const max = Math.max(...points.map((p) => p.value)) * 1.08;
  const min = Math.min(...points.map((p) => p.value)) * 0.9;
  const x = (i: number) => pl + (i * (w - pl - pr)) / Math.max(points.length - 1, 1);
  const y = (v: number) => pt + (h - pt - pb) * (1 - (v - min) / (max - min || 1));
  const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.value).toFixed(1)}`).join(" ");
  const ticks = [min, (min + max) / 2, max];
  const hp = hover !== null ? points[hover] : null;
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label={ariaLabel}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = (e.currentTarget as SVGSVGElement).getBoundingClientRect();
          const px = ((e.clientX - rect.left) / rect.width) * w;
          const i = Math.round(((px - pl) / (w - pl - pr)) * (points.length - 1));
          setHover(Math.max(0, Math.min(points.length - 1, i)));
        }}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pl} x2={w - pr} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
            <text x={pl - 6} y={y(t) + 4} textAnchor="end" fontSize="10" fill={MUTED}>{format(t)}</text>
          </g>
        ))}
        {points.map((p, i) => (i % 3 === 0 || i === points.length - 1) && (
          <text key={p.label} x={x(i)} y={h - 8} textAnchor="middle" fontSize="10" fill={MUTED}>{p.label.slice(5)}</text>
        ))}
        <path d={path} fill="none" stroke={SERIES} strokeWidth={2} strokeLinejoin="round" />
        {hp && hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pt} y2={h - pb} stroke={MUTED} strokeDasharray="3 3" strokeWidth={1} />
            <circle cx={x(hover)} cy={y(hp.value)} r={5} fill={SERIES} stroke="#fff" strokeWidth={2} />
          </g>
        )}
        <text x={x(points.length - 1)} y={y(points[points.length - 1].value) - 8} textAnchor="end" fontSize="11" fill={INK} fontWeight="600">
          {format(points[points.length - 1].value)}
        </text>
      </svg>
      {hp && (
        <div className="pointer-events-none absolute right-2 top-2 rounded border border-cream-300 bg-white px-2 py-1 text-xs shadow" role="status">
          Week of {hp.label}: <b>{format(hp.value)}</b>
        </div>
      )}
    </div>
  );
}

export function HBars({ items, format, ariaLabel }: { items: { label: string; value: number; note?: string }[]; format: (v: number) => string; ariaLabel: string }) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <ul className="space-y-1.5" aria-label={ariaLabel}>
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[140px_1fr_auto] items-center gap-2 text-xs" title={`${i.label}: ${format(i.value)}${i.note ? ` (${i.note})` : ""}`}>
          <span className="truncate text-navy-800">{i.label}</span>
          <span className="h-3 rounded-r bg-cream-200" aria-hidden>
            <span className="block h-3 rounded-r" style={{ width: `${(i.value / max) * 100}%`, background: SERIES }} />
          </span>
          <span className="font-mono text-navy-900">{format(i.value)}</span>
        </li>
      ))}
    </ul>
  );
}

export function DivergingBars({ items, ariaLabel }: { items: { label: string; value: number | null; sub?: string }[]; ariaLabel: string }) {
  const max = Math.max(5, ...items.map((i) => Math.abs(i.value ?? 0)));
  return (
    <ul className="space-y-2" aria-label={ariaLabel}>
      {items.map((i) => {
        const v = i.value ?? 0;
        const width = (Math.abs(v) / max) * 50;
        return (
          <li key={i.label} className="text-xs" title={`${i.label}: ${v > 0 ? "+" : ""}${v}%`}>
            <div className="flex justify-between text-navy-800"><span>{i.label}</span><span className="text-navy-600">{i.sub}</span></div>
            <div className="relative mt-0.5 h-3 bg-cream-100" aria-hidden>
              <span className="absolute left-1/2 top-0 h-3 w-px bg-navy-600" />
              <span className="absolute top-0 h-3" style={{ background: v >= 0 ? SERIES : LOSS, width: `${width}%`, left: v >= 0 ? "50%" : `${50 - width}%`, borderRadius: v >= 0 ? "0 4px 4px 0" : "4px 0 0 4px" }} />
            </div>
            <div className={`mt-0.5 font-mono ${v >= 0 ? "text-leaf-700" : "text-brick-700"}`}>{v > 0 ? "+" : ""}{v.toFixed(1)}% {v >= 0 ? "▲" : "▼"}</div>
          </li>
        );
      })}
    </ul>
  );
}

const STATUS: Record<string, { color: string; icon: string; label: string }> = {
  critical: { color: LOSS, icon: "●", label: "Critical" },
  reorder: { color: "#8a5a00", icon: "▲", label: "Reorder" },
  ok: { color: SERIES, icon: "✓", label: "OK" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STATUS[status] ?? { color: MUTED, icon: "•", label: status };
  return <span className="whitespace-nowrap text-xs font-semibold" style={{ color: s.color }}><span aria-hidden>{s.icon}</span> {s.label}</span>;
}

export function CoverBars({ items }: { items: { label: string; cover: number; lead: number; status: string }[] }) {
  const max = Math.max(...items.map((i) => Math.max(i.cover, i.lead)), 1) * 1.1;
  return (
    <ul className="space-y-1.5" aria-label="Days of stock cover against supplier lead time">
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[200px_1fr_auto] items-center gap-2 text-xs" title={`${i.label}: ${i.cover} days of cover, lead time ${i.lead} days`}>
          <span className="truncate text-navy-800">{i.label}</span>
          <span className="relative h-3 rounded-r bg-cream-200" aria-hidden>
            <span className="block h-3 rounded-r" style={{ width: `${(i.cover / max) * 100}%`, background: STATUS[i.status]?.color ?? MUTED }} />
            <span className="absolute top-[-3px] h-[18px] w-0.5 bg-navy-900" style={{ left: `${(i.lead / max) * 100}%` }} />
          </span>
          <span className="flex items-center gap-2"><span className="font-mono text-navy-900">{i.cover}d</span><StatusBadge status={i.status} /></span>
        </li>
      ))}
    </ul>
  );
}
