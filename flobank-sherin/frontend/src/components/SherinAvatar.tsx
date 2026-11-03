import { useState } from "react";

/** The single approved portrait. Every screen uses this one asset; no other face is generated or substituted. */
export const SHERIN_IMAGE = "/sherin/sherin-ghibli.png";

const SIZES = { xs: 24, sm: 32, md: 44, lg: 72, xl: 168 } as const;

export function SherinAvatar({ size = "md", ring = true, className = "" }: { size?: keyof typeof SIZES; ring?: boolean; className?: string }) {
  const [failed, setFailed] = useState(false);
  const px = SIZES[size];
  return (
    <span data-testid="sherin-avatar" data-src={SHERIN_IMAGE} data-size={size}
      className={`relative inline-flex shrink-0 overflow-hidden rounded-full bg-flo-100 ${ring ? "ring-2 ring-white shadow-[0_0_0_3px_rgba(19,121,91,0.25)]" : ""} ${className}`}
      style={{ width: px, height: px }} title={failed ? "Sherin (approved portrait pending: add public/sherin/sherin-ghibli.png)" : "Sherin"}>
      {!failed ? (
        <img src={SHERIN_IMAGE} alt="Sherin, FLO Bank's AI" width={px} height={px} className="h-full w-full object-cover" onError={() => setFailed(true)} />
      ) : (
        <svg viewBox="0 0 64 64" width={px} height={px} role="img" aria-label="Sherin (portrait pending)">
          <defs><linearGradient id="sg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#13795B" /><stop offset="1" stopColor="#0B3D2E" /></linearGradient></defs>
          <rect width="64" height="64" fill="url(#sg)" />
          <path d="M18 44c12 0 28-8 28-26-16 0-28 8-28 26z" fill="#E6F4EE" opacity=".95" />
          <path d="M18 44l15-15" stroke="#13795B" strokeWidth="2.4" strokeLinecap="round" />
        </svg>
      )}
    </span>
  );
}
