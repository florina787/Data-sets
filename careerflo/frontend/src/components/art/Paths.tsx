/** Original flat illustrations for the four growth paths (Ladder, Lattice, Wave, Portfolio) and the books-stairs mark. */
const INK = "#101828", V = "#7357FF", S = "#38BDF8", A = "#F5B971", C = "#F59E0B";

function Figure({ x, y, s = 1 }: { x: number; y: number; s?: number }) {
  return (
    <g transform={`translate(${x} ${y}) scale(${s})`}>
      <circle cx="0" cy="-34" r="7" fill={INK} />
      <path d="M-9 -24h18l3 22h-24Z" fill={C} />
      <path d="M-8 -2 -10 22M8 -2l4 24" stroke={S} strokeWidth="6" strokeLinecap="round" />
      <path d="M-9 -20-18-8M9 -20l10-14" stroke={C} strokeWidth="5" strokeLinecap="round" />
    </g>
  );
}

export function LadderArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 150" className={className} role="img" aria-label="Ladder: climbing">
      {[[30, 40, V], [52, 22, A], [150, 30, S], [168, 62, A], [38, 80, C]].map(([x, y, c], i) => (
        <g key={i}><ellipse cx={x as number} cy={y as number} rx="7" ry="9" fill={c as string} opacity=".85" /><path d={`M${x} ${(y as number) + 9}q-3 8 2 16`} stroke={INK} strokeOpacity=".3" fill="none" /></g>
      ))}
      <path d="M86 140 112 10M118 140 144 10" stroke={INK} strokeWidth="2.5" />
      {Array.from({ length: 7 }).map((_, i) => <path key={i} d={`M${90 + i * 3.7} ${122 - i * 18}h26`} stroke={INK} strokeWidth="2.5" />)}
      <Figure x={118} y={80} />
    </svg>
  );
}

export function LatticeArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 150" className={className} role="img" aria-label="Lattice: moving sideways">
      <g stroke={S} strokeOpacity=".6">{Array.from({ length: 9 }).map((_, i) => <path key={i} d={`M${10 + i * 22.5} 10v130`} />)}{Array.from({ length: 6 }).map((_, i) => <path key={i} d={`M10 ${10 + i * 26}h180`} />)}</g>
      <circle cx="18" cy="96" r="16" fill={S} /><circle cx="60" cy="48" r="7" fill={C} />
      <path d="M150 30l22 14-8 10-22-14Z" fill={C} /><path d="M140 140l40-40v40Z" fill={A} opacity=".8" />
      <path d="M100 18l16 22h-9v30h-14v-30h-9Z" fill={A} />
      <path d="M44 72l26-18v10h30v16h-30v10Z" fill="#3B82F6" /><path d="M156 72l-26-18v10h-30v16h30v10Z" fill={S} opacity=".7" />
      <Figure x={100} y={104} s={0.9} />
    </svg>
  );
}

export function WaveArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 150" className={className} role="img" aria-label="Wave: riding what is next">
      <path d="M10 112c30-14 50 10 80-2s40-38 70-30 30 22 30 22" stroke="#3B82F6" strokeWidth="2" fill="none" />
      <path d="M10 124c34-10 60 8 92-4s58-10 88 0" stroke={S} strokeWidth="2" fill="none" />
      <path d="M120 40c30-6 56 16 56 34" stroke={INK} strokeOpacity=".5" fill="none" />
      <path d="M58 106c20 8 70 8 92-2" stroke={A} strokeWidth="8" strokeLinecap="round" />
      {[[40, 40], [168, 30], [150, 60]].map(([x, y], i) => <path key={i} d={`M${x} ${y - 5}v10M${x - 5} ${y}h10`} stroke={C} strokeWidth="2" />)}
      <Figure x={104} y={80} />
    </svg>
  );
}

export function PortfolioArt({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 150" className={className} role="img" aria-label="Portfolio: proving it">
      <path d="M30 130h150" stroke={INK} strokeOpacity=".4" />
      <rect x="96" y="66" width="76" height="62" rx="10" fill={A} />
      <path d="M118 66v-10h32v10" stroke={INK} strokeWidth="3" fill="none" />
      <rect x="96" y="86" width="76" height="8" fill={C} opacity=".7" />
      <path d="M104 64l14-22 10 22M132 64l10-26 14 26" fill={S} opacity=".85" />
      <Figure x={64} y={108} />
    </svg>
  );
}

export const PATH_ART = { ladder: LadderArt, lattice: LatticeArt, wave: WaveArt, portfolio: PortfolioArt };

/** Books stacked as stairs, with a bookmark: the learning mark. */
export function BookStairs({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 160 110" className={className} role="img" aria-label="Books as stairs">
      {[0, 1, 2, 3].map((i) => (
        <g key={i} transform={`translate(${i * 18} ${70 - i * 18})`}>
          <path d="M8 18c0-10 10-14 22-10l70-0" stroke={INK} strokeWidth="5" fill="none" strokeLinecap="round" />
          <path d="M8 18c0 8 8 12 18 12h76" stroke={INK} strokeWidth="5" fill="none" strokeLinecap="round" />
        </g>
      ))}
      <path d="M6 104h150" stroke={INK} strokeWidth="5" strokeLinecap="round" />
      <path d="M96 76h14v22l-7-6-7 6Z" fill={V} />
    </svg>
  );
}
