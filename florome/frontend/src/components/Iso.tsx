// Isometric SVG primitives. Everything is generated from data, so the illustrations reflect real platform state.
const C = Math.cos(Math.PI / 6);
const S = 0.5;
const iso = (x: number, y: number, z = 0): [number, number] => [(x - y) * C, (x + y) * S - z];
const pts = (p: [number, number][]) => p.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(" ");

export function Slab({ x, y, z = 0, w, d, h, top, left, right, stroke = "#ffffff" }: {
  x: number; y: number; z?: number; w: number; d: number; h: number; top: string; left: string; right: string; stroke?: string;
}) {
  const t = [iso(x, y, z + h), iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x, y + d, z + h)];
  const l = [iso(x, y + d, z + h), iso(x + w, y + d, z + h), iso(x + w, y + d, z), iso(x, y + d, z)];
  const r = [iso(x + w, y, z + h), iso(x + w, y + d, z + h), iso(x + w, y + d, z), iso(x + w, y, z)];
  return (
    <g strokeWidth={0.8} stroke={stroke} strokeLinejoin="round">
      <polygon points={pts(l)} fill={left} />
      <polygon points={pts(r)} fill={right} />
      <polygon points={pts(t)} fill={top} />
    </g>
  );
}

export interface Satellite { label: string; x: number; y: number; active: boolean; glyph: string }

/** Light hero: stacked plates under a dome, satellite tiles for each platform group, dotted links to the core. */
export function DomeStack({ satellites }: { satellites: Satellite[] }) {
  const core = iso(0, 0, 70);
  return (
    <svg viewBox="-330 -170 660 380" className="h-full w-full" role="img" aria-label="Florome core with connected platform groups">
      <defs>
        <radialGradient id="ds-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#7C84F2" stopOpacity="0.35" />
          <stop offset="1" stopColor="#7C84F2" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ds-dome" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
          <stop offset="1" stopColor="#C7CCFF" stopOpacity="0.55" />
        </linearGradient>
      </defs>
      <ellipse cx="0" cy="40" rx="250" ry="120" fill="url(#ds-glow)" />
      {satellites.map((s) => {
        const [sx, sy] = iso(s.x, s.y, 18);
        return (
          <path key={`l-${s.label}`} d={`M${sx},${sy} Q${sx / 2},${(sy + core[1]) / 2 + 20} ${core[0]},${core[1] + 30}`}
            fill="none" stroke={s.active ? "#5B63E6" : "#A3AAFB"} strokeWidth={1.2} strokeDasharray={s.active ? "0" : "3 4"} opacity={s.active ? 0.9 : 0.6}>
            {s.active && <animate attributeName="stroke-dashoffset" from="20" to="0" dur="1.6s" repeatCount="indefinite" />}
          </path>
        );
      })}
      <Slab x={-75} y={-75} w={150} d={150} h={14} top="#EEF0FF" left="#C7CCFF" right="#E0E3FF" />
      <Slab x={-58} y={-58} z={14} w={116} d={116} h={14} top="#E0E3FF" left="#A3AAFB" right="#C7CCFF" />
      <Slab x={-42} y={-42} z={28} w={84} d={84} h={14} top="#ffffff" left="#7C84F2" right="#A3AAFB" />
      {Array.from({ length: 7 }).flatMap((_, i) => Array.from({ length: 7 }).map((__, j) => {
        const [px, py] = iso(-30 + i * 10, -30 + j * 10, 42);
        return <circle key={`${i}-${j}`} cx={px} cy={py} r={1.6} fill="#5B63E6" opacity={0.25 + ((i * j) % 5) / 8} />;
      }))}
      <path d={`M${core[0] - 70},${core[1] + 26} A70 52 0 0 1 ${core[0] + 70},${core[1] + 26}`} fill="url(#ds-dome)" stroke="#7C84F2" strokeWidth={1.2} />
      <path d={`M${core[0] - 40},${core[1] + 26} A40 30 0 0 1 ${core[0] + 40},${core[1] + 26}`} fill="none" stroke="#5B63E6" strokeWidth={1} opacity={0.6} />
      {satellites.map((s) => {
        const [lx, ly] = iso(s.x + 12, s.y + 12, 30);
        return (
          <g key={s.label}>
            <Slab x={s.x - 18} y={s.y - 18} w={36} d={36} h={8} top="#F6F6FC" left="#C7CCFF" right="#E0E3FF" />
            <Slab x={s.x - 13} y={s.y - 13} z={8} w={26} d={26} h={10} top={s.active ? "#ffffff" : "#F6F6FC"} left={s.active ? "#7C84F2" : "#C7CCFF"} right={s.active ? "#A3AAFB" : "#E0E3FF"} />
            <text x={lx - 14} y={ly + 2} textAnchor="middle" fontSize="15">{s.glyph}</text>
            <text x={lx - 14} y={ly + 44} textAnchor="middle" fontSize="10" fill="#4A4E6E" fontFamily="ui-monospace, monospace">{s.label}</text>
          </g>
        );
      })}
    </svg>
  );
}

export interface CubeNode { id: string; label: string; x: number; y: number; state: "core" | "verified" | "implemented" | "planned" }

function Cube({ x, y, size, state }: { x: number; y: number; size: number; state: CubeNode["state"] }) {
  const s = size;
  const top = [[x, y - s], [x + s * C, y - s / 2], [x, y], [x - s * C, y - s / 2]] as [number, number][];
  const left = [[x - s * C, y - s / 2], [x, y], [x, y + s], [x - s * C, y + s / 2]] as [number, number][];
  const right = [[x, y], [x + s * C, y - s / 2], [x + s * C, y + s / 2], [x, y + s]] as [number, number][];
  const fill = state === "core" ? ["#7C84F2", "#4A4FD1", "#5B63E6"] : state === "verified" ? ["#2a2f6b", "#1b1f4a", "#232858"] : ["#15172b", "#0c0d1c", "#111327"];
  const stroke = state === "planned" ? "#ffffff55" : state === "implemented" ? "#ffffff80" : "#C7CCFF";
  return (
    <g stroke={stroke} strokeWidth={1.1} strokeLinejoin="round" strokeDasharray={state === "planned" ? "3 3" : undefined}>
      <polygon points={pts(left)} fill={fill[1]} />
      <polygon points={pts(right)} fill={fill[2]} />
      <polygon points={pts(top)} fill={fill[0]} />
      {state !== "planned" && <circle cx={x + s * 0.35} cy={y + s * 0.15} r={2} fill={state === "core" ? "#fff" : "#A3AAFB"} stroke="none" />}
    </g>
  );
}

/** Dark integration network: Florome is the lit core; each platform cube is styled by its real implementation state. */
export function CubeNetwork({ nodes }: { nodes: CubeNode[] }) {
  const core = nodes.find((n) => n.state === "core");
  return (
    <svg viewBox="-300 -190 600 380" className="h-full w-full" role="img" aria-label="Integration network: Florome core and platform connectors">
      {core && nodes.filter((n) => n !== core).map((n) => (
        <line key={`e-${n.id}`} x1={core.x} y1={core.y} x2={n.x} y2={n.y} stroke={n.state === "planned" ? "#ffffff18" : "#A3AAFB"}
          strokeWidth={1} strokeDasharray={n.state === "planned" ? "2 5" : "0"} opacity={n.state === "verified" ? 0.9 : 0.5} />
      ))}
      {nodes.map((n) => (
        <g key={n.id}>
          <Cube x={n.x} y={n.y} size={n.state === "core" ? 44 : 24} state={n.state} />
          <text x={n.x} y={n.y + (n.state === "core" ? 66 : 40)} textAnchor="middle" fontSize={n.state === "core" ? 12 : 9.5}
            fill={n.state === "planned" ? "#ffffff8c" : "#ffffffdd"} fontFamily="ui-monospace, monospace">{n.label}</text>
        </g>
      ))}
    </svg>
  );
}
