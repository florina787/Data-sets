import { cn } from "./ui";

/** FLO mark: an "F" built from three parallel, forward-leaning strokes (momentum) on a calm indigo tile. */
export function LogoMark({ className, title = "FLO" }: { className?: string; title?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={cn("h-8 w-8", className)} role="img" aria-label={title}>
      <defs>
        <linearGradient id="flo-tile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6B76F5" />
          <stop offset="1" stopColor="#3D46C9" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill="url(#flo-tile)" />
      <polygon points="9,31 14.3,31 20.7,9 15.4,9" fill="#FFFFFF" />
      <polygon points="22.1,9 32.3,9 30.73,14.4 20.53,14.4" fill="#FFFFFF" />
      <polygon points="19.3,18.6 27.5,18.6 26.05,23.6 17.85,23.6" fill="#FFFFFF" opacity="0.8" />
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
