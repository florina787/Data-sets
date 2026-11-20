// Florome mark: concentric dome arcs over a horizon, a canopy covering everything beneath it.
export function DomeMark({ size = 32, dark = false }: { size?: number; dark?: boolean }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <defs>
        <linearGradient id="fm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#A3AAFB" />
          <stop offset="1" stopColor="#3B3DAA" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill={dark ? "#ffffff14" : "#14164A"} />
      <path d="M12 44a20 20 0 0 1 40 0" fill="none" stroke="url(#fm-g)" strokeWidth="6" strokeLinecap="round" />
      <path d="M22 44a10 10 0 0 1 20 0" fill="none" stroke="#C7CCFF" strokeWidth="4" strokeLinecap="round" />
      <circle cx="32" cy="44" r="4" fill="#fff" />
      <path d="M8 48h48" stroke="#5B63E6" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

export function Wordmark({ dark = false }: { dark?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <DomeMark size={30} dark={dark} />
      <span className={`font-display text-[19px] font-semibold tracking-tight ${dark ? "text-white" : "text-ink"}`}>florome</span>
    </span>
  );
}
