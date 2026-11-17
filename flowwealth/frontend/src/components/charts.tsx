import { useEffect, useMemo, useRef } from "react";

/** Glowing dot-field area chart: stacked dots under the price line, blue -> violet. */
export function DotField({ values, height = 300, label }: { values: number[]; height?: number; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const c = ref.current;
    const ctx = c?.getContext?.("2d");
    if (!c || !ctx || values.length < 2) return;
    const dpr = window.devicePixelRatio || 1;
    const w = c.clientWidth, h = height;
    c.width = w * dpr; c.height = h * dpr; ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);
    const min = Math.min(...values), max = Math.max(...values);
    const pad = (max - min) * 0.12 || 1;
    const lo = min - pad, hi = max + pad;
    const y = (v: number) => h - 8 - ((v - lo) / (hi - lo)) * (h - 24);
    const cols = Math.min(Math.floor(w / 5), 260);
    const at = (i: number) => {
      const f = (i / (cols - 1)) * (values.length - 1);
      const a = Math.floor(f), b = Math.min(a + 1, values.length - 1);
      return values[a] + (values[b] - values[a]) * (f - a);
    };
    // deterministic jitter so redraws do not shimmer
    let seed = 7;
    const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
    for (let i = 0; i < cols; i++) {
      const x = (i / (cols - 1)) * (w - 4) + 2;
      const top = y(at(i));
      const t = i / (cols - 1);
      const r = Math.round(79 + (166 - 79) * t), g = Math.round(124 + (107 - 124) * t), bl = 255;
      for (let yy = top; yy < h; yy += 4 + (yy - top) * 0.06) {
        const depth = (yy - top) / (h - top + 1);
        const alpha = Math.max(0.05, 0.9 * (1 - depth) ** 2.2);
        ctx.fillStyle = `rgba(${r},${g},${bl},${alpha})`;
        ctx.beginPath();
        ctx.arc(x + (rnd() - 0.5) * 2.2, yy, depth < 0.08 ? 1.5 : 1, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.shadowColor = "rgba(140,160,255,.9)"; ctx.shadowBlur = 12;
    ctx.strokeStyle = "rgba(200,210,255,.9)"; ctx.lineWidth = 1.2;
    ctx.beginPath();
    for (let i = 0; i < cols; i++) {
      const x = (i / (cols - 1)) * (w - 4) + 2;
      if (i === 0) ctx.moveTo(x, y(at(i))); else ctx.lineTo(x, y(at(i)));
    }
    ctx.stroke();
  }, [values, height]);
  const first = values[0], last = values[values.length - 1];
  return (
    <figure style={{ margin: 0 }}>
      <canvas ref={ref} className="dotfield" style={{ height }} role="img"
        aria-label={`${label}: ${values.length} points, from ${first?.toFixed(2)} to ${last?.toFixed(2)}`} />
    </figure>
  );
}

export function Sparkline({ values, width = 90, height = 26, color }: { values: number[]; width?: number; height?: number; color?: string }) {
  const d = useMemo(() => {
    if (values.length < 2) return "";
    const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
    return values.map((v, i) => `${i ? "L" : "M"}${((i / (values.length - 1)) * width).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`).join(" ");
  }, [values, width, height]);
  const up = values.length > 1 && values[values.length - 1] >= values[0];
  return (
    <svg width={width} height={height} aria-hidden="true">
      <path d={d} fill="none" stroke={color ?? (up ? "var(--up)" : "var(--down)")} strokeWidth={1.4} strokeLinecap="round" />
    </svg>
  );
}

/** Area/line chart for index levels. */
export function AreaChart({ values, height = 220, labels }: { values: number[]; height?: number; labels?: string[] }) {
  const w = 800;
  const { path, area, min, max } = useMemo(() => {
    const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
    const pts = values.map((v, i) => [(i / Math.max(values.length - 1, 1)) * w, height - 20 - ((v - min) / span) * (height - 40)]);
    const path = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    return { path, area: `${path} L${w},${height} L0,${height} Z`, min, max };
  }, [values, height]);
  return (
    <svg viewBox={`0 0 ${w} ${height}`} width="100%" height={height} preserveAspectRatio="none" role="img"
      aria-label={`Index from ${values[0]?.toFixed(1)} to ${values[values.length - 1]?.toFixed(1)}; range ${min.toFixed(1)}–${max.toFixed(1)}`}>
      <defs>
        <linearGradient id="ag" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="rgba(63,214,139,.35)" /><stop offset="1" stopColor="rgba(63,214,139,0)" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#ag)" />
      <path d={path} fill="none" stroke="var(--up)" strokeWidth={1.6} vectorEffect="non-scaling-stroke" />
      {labels && <title>{labels[0]} → {labels[labels.length - 1]}</title>}
    </svg>
  );
}

/** Semicircle gauge (e.g. market breadth). value in [0,1]. */
export function Gauge({ value, label, sub }: { value: number; label: string; sub?: string }) {
  const r = 70, cx = 90, cy = 86, a = Math.PI * (1 - Math.max(0, Math.min(1, value)));
  const arc = (from: number, to: number) => {
    const p = (t: number) => [cx + r * Math.cos(t), cy - r * Math.sin(t)];
    const [x1, y1] = p(from), [x2, y2] = p(to);
    return `M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2}`;
  };
  return (
    <svg viewBox="0 0 180 100" width="100%" style={{ maxWidth: 240 }} role="img" aria-label={`${label}: ${(value * 100).toFixed(0)}%`}>
      <path d={arc(Math.PI, 0)} stroke="rgba(255,255,255,.08)" strokeWidth={14} fill="none" strokeLinecap="round" />
      <path d={arc(Math.PI, a)} stroke="var(--up)" strokeWidth={14} fill="none" strokeLinecap="round" />
      <text x={cx} y={cy - 18} textAnchor="middle" fill="var(--text)" fontSize="13" fontWeight="600">{label}</text>
      <text x={cx} y={cy} textAnchor="middle" fill="var(--muted)" fontSize="11">{sub}</text>
    </svg>
  );
}

const SEG_COLORS = ["#3fd68b", "#8fdc4f", "#d9d84a", "#ffb547", "#ff7a2f", "#ff4d3d"];
/** Segmented meter: `segments` bars, `on` lit, colour runs green -> red. */
export function SegmentedMeter({ on, segments = 40, label }: { on: number; segments?: number; label: string }) {
  return (
    <div className="seg" role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={segments} aria-valuenow={on}>
      {Array.from({ length: segments }, (_, i) => {
        const c = SEG_COLORS[Math.min(SEG_COLORS.length - 1, Math.floor((i / segments) * SEG_COLORS.length))];
        return <i key={i} className={i < on ? "on" : ""} style={{ background: c, color: c }} />;
      })}
    </div>
  );
}

export function MiniBars({ values }: { values: number[] }) {
  const max = Math.max(...values.map(Math.abs), 1e-9);
  return (
    <span className="minibars" aria-hidden="true">
      {values.map((v, i) => <i key={i} style={{ height: `${Math.max(12, (Math.abs(v) / max) * 100)}%`, background: v >= 0 ? "var(--up)" : "var(--down)" }} />)}
    </span>
  );
}
