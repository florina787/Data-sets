import { cn } from "./ui";

/** FLO mark: an "F" built from three parallel, forward-leaning strokes (momentum) inside a calm navy tile. */
export function LogoMark({ className, title = "FLO" }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("h-8 w-8", className)} role="img" aria-label={title}>
      <defs>
        <linearGradient id="flo-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1E2E52" />
          <stop offset="1" stopColor="#0B1220" />
        </linearGradient>
        <linearGradient id="flo-gold" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#F2D57A" />
          <stop offset="1" stopColor="#C9971C" />
        </linearGradient>
      </defs>
      <rect x="0.75" y="0.75" width="38.5" height="38.5" rx="10" fill="url(#flo-tile)" stroke="#D4AF37" strokeOpacity="0.45" strokeWidth="1.5" />
      <polygon points="9,31 14.3,31 20.7,9 15.4,9" fill="url(#flo-gold)" />
      <polygon points="22.1,9 32.3,9 30.73,14.4 20.53,14.4" fill="url(#flo-gold)" />
      <polygon points="19.3,18.6 27.5,18.6 26.05,23.6 17.85,23.6" fill="url(#flo-gold)" opacity="0.85" />
    </svg>
  );
}

export function Logo({ collapsed = false, tagline = "Investment Intelligence" }: { collapsed?: boolean; tagline?: string }) {
  return (
    <div className="flex items-center gap-2.5">
      <LogoMark />
      {!collapsed && (
        <div className="leading-tight">
          <div className="text-[15px] font-semibold tracking-[0.22em] text-ink">FLO</div>
          <div className="text-[10px] uppercase tracking-[0.14em] text-muted">{tagline}</div>
        </div>
      )}
    </div>
  );
}
