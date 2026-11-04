import { useId } from "react";

// Original vector illustrations for Flo & Jerry (drawn for this project, no third-party artwork):
// Jerry as a smiling fries carton, a potato, loose fries, and the potato-to-fries banner.
// Colours: carton red #e0525a → #a8262f, fries gold #f7dc7a / #e9b95b, potato #c4935f → #8a5a32.

const FRY_X = [10, 15, 20, 25, 30, 35];
const FRY_TOP = [10, 5, 8, 3, 7, 11];

export function FriesCarton({ size = 40, label = "Jerry, the AI assistant" }: { size?: number; label?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" role={label ? "img" : undefined} aria-label={label || undefined} aria-hidden={label ? undefined : true}>
      <defs>
        <linearGradient id={`${id}c`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#e65b63" /><stop offset="1" stopColor="#a8262f" /></linearGradient>
        <linearGradient id={`${id}f`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#fbe58f" /><stop offset="1" stopColor="#e9b95b" /></linearGradient>
      </defs>
      <rect x="1" y="1" width="46" height="46" rx="14" fill="#0c1e35" stroke="#233b58" />
      {FRY_X.map((x, i) => (
        <rect key={x} x={x - 2} y={FRY_TOP[i]} width="4.4" height="26" rx="1.2" fill={`url(#${id}f)`}
          stroke="#c9963a" strokeWidth="0.5" transform={`rotate(${(i - 2.5) * 3} ${x} 30)`} />
      ))}
      <path d="M8 20 h32 l-3.2 22 a2 2 0 0 1 -2 1.7 h-21.6 a2 2 0 0 1 -2 -1.7 z" fill={`url(#${id}c)`} />
      <path d="M8 20 h32 l-0.4 3 h-31.2 z" fill="#ffffff" opacity="0.18" />
      <path d="M17.5 30 q1.6 -1.8 3.2 0" stroke="#1b2440" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M27.3 30 q1.6 -1.8 3.2 0" stroke="#1b2440" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <path d="M21.5 34 q2.5 2.2 5 0" stroke="#1b2440" strokeWidth="1.6" fill="none" strokeLinecap="round" />
      <circle cx="16" cy="33.2" r="1.4" fill="#ff9aa2" opacity="0.7" />
      <circle cx="32" cy="33.2" r="1.4" fill="#ff9aa2" opacity="0.7" />
    </svg>
  );
}

export function Potato({ size = 64, spots = true, label }: { size?: number; spots?: boolean; label?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size * 1.1} viewBox="0 0 100 110" role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <radialGradient id={`${id}p`} cx="0.38" cy="0.32" r="0.8"><stop offset="0" stopColor="#d9a874" /><stop offset="0.65" stopColor="#b9864f" /><stop offset="1" stopColor="#8a5a32" /></radialGradient>
      </defs>
      <path d="M52 6 C78 4 94 30 92 58 C90 88 70 106 46 104 C20 102 6 82 9 56 C12 30 26 8 52 6 Z" fill={`url(#${id}p)`} />
      <path d="M30 22 C38 14 50 12 60 14" stroke="#f3d3a8" strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.5" />
      {spots && (
        <g fill="#7a4a26" opacity="0.75">
          <circle cx="38" cy="40" r="1.8" /><circle cx="62" cy="34" r="1.4" /><circle cx="55" cy="66" r="2" />
          <circle cx="34" cy="74" r="1.5" /><circle cx="70" cy="80" r="1.6" /><circle cx="47" cy="88" r="1.2" />
          <path d="M60 52 q5 -2 8 2" stroke="#7a4a26" strokeWidth="1.4" fill="none" strokeLinecap="round" />
        </g>
      )}
    </svg>
  );
}

export function Fries({ width = 110 }: { width?: number }) {
  const id = useId().replace(/:/g, "");
  // A tidy pile: parallel sticks leaning right, with a few on top leaning the other way.
  const sticks: [number, number, number, number][] = [
    [18, 34, 28, 64], [30, 30, 28, 66], [42, 28, 28, 66], [54, 30, 28, 64], [66, 34, 28, 60],
    [36, 40, -24, 58], [52, 44, -24, 54], [26, 52, 62, 50], [70, 56, 62, 44],
  ];
  return (
    <svg width={width} height={width * 0.9} viewBox="0 0 120 108" aria-hidden>
      <defs>
        <linearGradient id={`${id}s`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#fbe58f" /><stop offset="0.6" stopColor="#f2cd6a" /><stop offset="1" stopColor="#d9a441" /></linearGradient>
      </defs>
      {sticks.map(([x, y, rot, len]) => (
        <g key={`${x}-${y}`} transform={`rotate(${rot} ${x + 4} ${y + len / 2})`}>
          <rect x={x} y={y} width="9" height={len} rx="1.5" fill={`url(#${id}s)`} />
          <rect x={x} y={y} width="9" height="5" rx="1.5" fill="#fff3c4" opacity="0.8" />
        </g>
      ))}
    </svg>
  );
}

/** Executive banner: the journey from a raw potato to finished fries. */
export function FieldToFriesBanner() {
  return (
    <div className="relative overflow-hidden rounded-2xl border border-surface-line bg-gradient-to-r from-surface-card via-[#0f2a4a] to-surface-card px-5 py-4 shadow-card">
      <div className="pointer-events-none absolute -right-10 -top-16 h-48 w-48 rounded-full bg-gold-400/10 blur-2xl" aria-hidden />
      <div className="relative flex flex-wrap items-center justify-between gap-4">
        <div className="max-w-xl">
          <div className="label text-gold-300">From field to fries</div>
          <p className="mt-1 text-lg font-semibold leading-snug text-navy-900">Inspect every potato, protect yield, and ship consistent fries, with every figure traceable to its data.</p>
          <p className="mt-1 text-xs text-navy-600">Illustration only. Figures on this page come from the synthetic dataset and live demo records.</p>
        </div>
        <div className="flex items-center gap-3" aria-hidden>
          <Potato size={58} />
          <svg width="56" height="16" viewBox="0 0 56 16"><path d="M2 8 H48" stroke="#38bdf8" strokeWidth="2" strokeDasharray="4 4" /><path d="M46 3 L54 8 L46 13" fill="none" stroke="#38bdf8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" /></svg>
          <Fries width={92} />
          <FriesCarton size={64} label="" />
        </div>
      </div>
    </div>
  );
}
