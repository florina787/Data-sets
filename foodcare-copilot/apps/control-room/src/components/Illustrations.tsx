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

/** Potatoes orbiting Jerry: CSS transform animation, paused on hover, off with reduced motion. */
export function PotatoOrbit() {
  return (
    <div className="orbit shrink-0" aria-hidden>
      <div className="orbit-ring" />
      <div className="orbit-center"><FriesCarton size={72} label="" /></div>
      <div className="orbit-item"><div className="orbit-spin"><Potato size={40} /></div></div>
      <div className="orbit-item"><div className="orbit-spin" style={{ animationDuration: "9s" }}><Potato size={36} /></div></div>
      <div className="orbit-item"><div className="orbit-spin" style={{ animationDuration: "6s", animationDirection: "reverse" }}><Potato size={42} /></div></div>
    </div>
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
        <PotatoOrbit />
      </div>
    </div>
  );
}


/** Original inspection camera on a gimbal; its lens is drawn as a glass eye. */
export function InspectionCamera({ width = 340 }: { width?: number }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={width} height={width * 0.95} viewBox="0 0 360 340" aria-hidden>
      <defs>
        <linearGradient id={`${id}body`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3a4658" /><stop offset="0.5" stopColor="#1f2733" /><stop offset="1" stopColor="#0b1018" /></linearGradient>
        <linearGradient id={`${id}arm`} x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#141b26" /><stop offset="0.6" stopColor="#2b3545" /><stop offset="1" stopColor="#10161f" /></linearGradient>
        <radialGradient id={`${id}glass`} cx="0.4" cy="0.35" r="0.75"><stop offset="0" stopColor="#dbe9ff" stopOpacity="0.9" /><stop offset="0.35" stopColor="#5b8cff" /><stop offset="0.75" stopColor="#1d3c8f" /><stop offset="1" stopColor="#081633" /></radialGradient>
        <radialGradient id={`${id}glow`} cx="0.5" cy="0.5" r="0.5"><stop offset="0" stopColor="#7fb2ff" stopOpacity="0.45" /><stop offset="1" stopColor="#7fb2ff" stopOpacity="0" /></radialGradient>
      </defs>
      <ellipse cx="190" cy="318" rx="120" ry="14" fill="#000" opacity="0.45" />
      <path d="M110 300 L150 262 H230 L270 300 Z" fill={`url(#${id}arm)`} />
      <rect x="168" y="196" width="44" height="70" rx="10" fill={`url(#${id}arm)`} />
      <path d="M212 120 h34 a12 12 0 0 1 12 12 v74 a12 12 0 0 1 -12 12 h-46 v-26 h32 v-46 h-20 z" fill={`url(#${id}arm)`} />
      <rect x="60" y="70" width="170" height="130" rx="26" fill={`url(#${id}body)`} />
      <rect x="66" y="76" width="158" height="18" rx="9" fill="#ffffff" opacity="0.06" />
      <circle cx="122" cy="138" r="70" fill={`url(#${id}glow)`} />
      <circle cx="122" cy="138" r="50" fill="#0a0f17" stroke="#3a4658" strokeWidth="3" />
      <circle cx="122" cy="138" r="38" fill={`url(#${id}glass)`} />
      <circle cx="122" cy="138" r="14" fill="#06102a" />
      <circle cx="110" cy="124" r="7" fill="#ffffff" opacity="0.85" />
      <circle cx="134" cy="152" r="3" fill="#ffffff" opacity="0.5" />
      <circle cx="206" cy="96" r="4" fill="#38bdf8" />
    </svg>
  );
}

/** Executive hero: night field, giant wordmark, the camera scanning a potato. Decorative only. */
export function CinematicHero() {
  return (
    <section className="hero relative overflow-hidden rounded-3xl border border-white/10" aria-label="Flo & Jerry">
      <div className="hero-stars pointer-events-none absolute inset-0" aria-hidden />
      <svg className="pointer-events-none absolute inset-x-0 bottom-0 w-full" viewBox="0 0 1200 160" preserveAspectRatio="none" height="120" aria-hidden>
        <path d="M0 120 C 200 70, 380 110, 560 80 S 900 60, 1200 100 V160 H0 Z" fill="#0a1a33" />
        <path d="M0 140 C 260 110, 520 150, 780 118 S 1050 110, 1200 130 V160 H0 Z" fill="#06101f" />
      </svg>
      <div className="relative grid min-h-[340px] items-end gap-6 px-6 pb-8 pt-10 md:px-10 lg:grid-cols-[1fr_auto]">
        <div className="relative z-10">
          <div className="label text-ice-300">Food Copilot 2.0</div>
          <h2 className="hero-word mt-2 select-none font-semibold leading-[0.85] tracking-[-0.045em]">Flo &amp; Jerry</h2>
          <p className="mt-4 max-w-xl text-base text-navy-700">Inspect every potato. Protect yield. Trace every figure to its data.</p>
          <p className="mt-1 text-xs text-navy-600">Illustration only. Figures below come from the synthetic dataset and live demo records.</p>
        </div>
        <div className="relative hidden h-[300px] w-[460px] lg:block" aria-hidden>
          <svg className="absolute inset-0" viewBox="0 0 460 300" width="460" height="300">
            <defs>
              <linearGradient id="hero-beam" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#bcd6ff" stopOpacity="0.38" /><stop offset="1" stopColor="#bcd6ff" stopOpacity="0" /></linearGradient>
            </defs>
            <polygon points="300,118 40,200 120,290" fill="url(#hero-beam)" />
            <line x1="300" y1="118" x2="40" y2="200" stroke="#bcd6ff" strokeOpacity="0.5" strokeDasharray="3 5" />
            <line x1="300" y1="118" x2="120" y2="290" stroke="#bcd6ff" strokeOpacity="0.5" strokeDasharray="3 5" />
            {[[38, 196, 1, 1], [128, 196, -1, 1], [38, 288, 1, -1], [128, 288, -1, -1]].map(([x, y, dx, dy]) => (
              <path key={`${x}-${y}`} d={`M${x} ${y + 14 * dy} V${y} H${x + 14 * dx}`} fill="none" stroke="#e8f0ff" strokeWidth="2.5" strokeLinecap="round" />
            ))}
          </svg>
          <div className="absolute left-[52px] top-[206px]"><Potato size={66} /></div>
          <div className="absolute right-0 top-0"><InspectionCamera width={250} /></div>
          <div className="absolute bottom-1 right-6 flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[11px] text-navy-800 backdrop-blur-sm">
            <FriesCarton size={22} label="" /> Jerry is watching the line
          </div>
        </div>
      </div>
    </section>
  );
}
