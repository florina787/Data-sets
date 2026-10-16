// Original MedAccess AI identity: circular emblem, rounded medical cross, heartbeat line and
// connected AI nodes. Not derived from any hospital's or protected medical emblem.
import { useId } from "react";

interface EmblemProps {
  size?: number;
  className?: string;
  title?: string;
}

export function MedAccessEmblem({ size = 40, className, title = "MedAccess AI emblem" }: EmblemProps) {
  const id = useId().replace(/:/g, "");
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} role="img" aria-label={title}>
      <defs>
        <linearGradient id={`g${id}`} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#1565C0" />
          <stop offset="1" stopColor="#00897B" />
        </linearGradient>
      </defs>
      <circle cx="32" cy="32" r="30" fill={`url(#g${id})`} />
      <circle cx="32" cy="32" r="26.5" fill="none" stroke="#fff" strokeOpacity=".35" strokeWidth="1.2" />
      <path d="M27.5 15h9a1.5 1.5 0 0 1 1.5 1.5V26h9.5a1.5 1.5 0 0 1 1.5 1.5v9a1.5 1.5 0 0 1-1.5 1.5H38v9.5a1.5 1.5 0 0 1-1.5 1.5h-9a1.5 1.5 0 0 1-1.5-1.5V38h-9.5A1.5 1.5 0 0 1 15 36.5v-9a1.5 1.5 0 0 1 1.5-1.5H26v-9.5a1.5 1.5 0 0 1 1.5-1.5z" fill="#fff" />
      <path d="M17 33h7l2.6-5 4 10 3.4-8 2 3H47" fill="none" stroke="#00897B" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      <g fill="#fff">
        <circle cx="50" cy="15" r="2.3" />
        <circle cx="56" cy="24" r="1.7" />
        <circle cx="46" cy="9" r="1.5" />
      </g>
      <path d="M50 15l6 9M50 15l-4-6" stroke="#fff" strokeWidth="1" strokeOpacity=".8" />
    </svg>
  );
}

export function MedAccessLogo({ compact = false, dark = false }: { compact?: boolean; dark?: boolean }) {
  return (
    <div className="flex items-center gap-2.5" aria-label="MedAccess AI">
      <MedAccessEmblem size={compact ? 32 : 40} title="" />
      {!compact && (
        <div className="leading-tight">
          <div className={`text-lg font-extrabold tracking-tight ${dark ? "text-white" : "text-ink"}`}>
            MedAccess<span className="text-teal"> AI</span>
          </div>
          <div className={`text-[10px] font-medium uppercase tracking-[0.14em] ${dark ? "text-teal-100" : "text-slate-500"}`}>
            Healthcare access intelligence
          </div>
        </div>
      )}
    </div>
  );
}

export function CopilotBadge({ size = 28 }: { size?: number }) {
  return (
    <span className="relative inline-flex" aria-hidden="true">
      <MedAccessEmblem size={size} title="" />
      <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-ok" />
    </span>
  );
}

export function LoadingLogo({ label = "Loading MedAccess AI…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-3 py-16" role="status" aria-live="polite">
      <MedAccessEmblem size={64} className="ch-warn" title="" />
      <span className="muted">{label}</span>
    </div>
  );
}
