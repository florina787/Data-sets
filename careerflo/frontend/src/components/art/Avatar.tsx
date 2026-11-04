import { cn } from "@/lib/utils";

const GRADS = [["#7357FF", "#38BDF8"], ["#F59E0B", "#F97066"], ["#10B981", "#38BDF8"], ["#101828", "#7357FF"], ["#F97066", "#7357FF"]];

/** Original generative avatar (initials on a gradient) — no stock photography. */
export function Avatar({ name, size = 40, className }: { name: string; size?: number; className?: string }) {
  const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?";
  const h = [...name].reduce((a, c) => a + c.charCodeAt(0), 0);
  const [a, b] = GRADS[h % GRADS.length];
  return (
    <div className={cn("grid shrink-0 place-items-center rounded-full font-semibold text-white", className)}
      style={{ width: size, height: size, fontSize: size * 0.36, background: `linear-gradient(135deg, ${a}, ${b})` }}>
      {initials}
    </div>
  );
}

/** Portrait-card figure: an abstract bust built from the person's colours. */
export function Bust({ seed, className }: { seed: string; className?: string }) {
  const h = [...seed].reduce((a, c) => a + c.charCodeAt(0), 0);
  const [a, b] = GRADS[h % GRADS.length];
  return (
    <svg viewBox="0 0 120 120" preserveAspectRatio="xMidYMid slice" className={className} aria-hidden>
      <defs><linearGradient id={`g${h}`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor={a} /><stop offset="1" stopColor={b} /></linearGradient></defs>
      <rect width="120" height="120" fill={`url(#g${h})`} opacity=".14" />
      <circle cx="60" cy="48" r="20" fill={`url(#g${h})`} />
      <path d="M22 120c4-26 20-40 38-40s34 14 38 40Z" fill={`url(#g${h})`} opacity=".85" />
      <circle cx="60" cy="48" r="20" fill="none" stroke="white" strokeOpacity=".5" />
    </svg>
  );
}
