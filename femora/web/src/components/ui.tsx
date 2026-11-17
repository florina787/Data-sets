// Theme-agnostic primitives. They only use token-backed classes, so a redesign is a tokens.css change.
import type { ButtonHTMLAttributes, ReactNode } from "react";

export function Card({ children, className = "", title, actions }: { children: ReactNode; className?: string; title?: ReactNode; actions?: ReactNode }) {
  return (
    <section className={`rounded-f bg-surface p-5 shadow-f ${className}`}>
      {(title || actions) && <div className="mb-3 flex items-center justify-between gap-3">{title && <h2 className="font-display text-lg">{title}</h2>}{actions}</div>}
      {children}
    </section>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" };
export function Button({ variant = "secondary", size = "md", className = "", ...p }: BtnProps) {
  const v = {
    primary: "bg-primary text-primary-ink hover:opacity-90",
    secondary: "bg-surface-2 text-ink hover:bg-line",
    ghost: "text-primary hover:bg-surface-2",
    danger: "bg-danger text-white hover:opacity-90",
  }[variant];
  const s = size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-[15px]";
  return <button type="button" {...p} className={`inline-flex items-center justify-center gap-2 rounded-full font-medium disabled:opacity-50 ${v} ${s} ${className}`} />;
}

export type Tone = "neutral" | "primary" | "accent" | "good" | "warn" | "danger";
const toneCls: Record<Tone, string> = {
  neutral: "bg-surface-2 text-muted",
  primary: "bg-primary/12 text-primary",
  accent: "bg-accent/12 text-accent",
  good: "bg-good/12 text-good",
  warn: "bg-warn/15 text-warn",
  danger: "bg-danger/12 text-danger",
};
export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: Tone; title?: string }) {
  return <span title={title} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${toneCls[tone]}`}>{children}</span>;
}

/** Status labels required by the brief: every capability says what it really is. */
export type Status = "demonstrated" | "simulated" | "planned" | "validated";
export function StatusBadge({ status }: { status: Status }) {
  const map: Record<Status, [string, Tone, string]> = {
    demonstrated: ["Available", "good", "Works today in this app"],
    simulated: ["Preview", "warn", "Partially available; see notes on the page"],
    planned: ["Coming", "neutral", "On the roadmap, not built yet"],
    validated: ["Clinically validated", "primary", "Passed clinical evaluation"],
  };
  const [label, tone, title] = map[status];
  return <Badge tone={tone} title={title}>{label}</Badge>;
}

export function Progress({ value, max, color = "var(--f-primary)", label }: { value: number; max: number; color?: string; label: string }) {
  const pct = max > 0 ? Math.min(value / max, 1) * 100 : 0;
  return (
    <div role="progressbar" aria-label={label} aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={max} className="h-2 overflow-hidden rounded-full bg-surface-2">
      <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

export function Notice({ children, tone = "warn" }: { children: ReactNode; tone?: Tone }) {
  return <div role="note" className={`rounded-f-sm px-3 py-2 text-sm ${toneCls[tone]} normal-case`}>{children}</div>;
}

export const inputCls = "w-full rounded-f-sm border border-line bg-surface px-3 py-2 text-[15px] text-ink placeholder:text-muted";

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs text-muted">{hint}</span>}
    </label>
  );
}

export function PageHeader({ title, sub, actions, status }: { title: string; sub?: ReactNode; actions?: ReactNode; status?: Status }) {
  return (
    <header className="f-enter mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <div className="flex items-center gap-2"><h1 className="font-display text-4xl">{title}</h1>{status && <StatusBadge status={status} />}</div>
        {sub && <p className="mt-1 max-w-2xl text-muted">{sub}</p>}
      </div>
      {actions}
    </header>
  );
}

export function Logo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <linearGradient id="femora-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#f0dcb0" /><stop offset=".6" stopColor="#b8935a" /><stop offset="1" stopColor="#3a2e1f" /></linearGradient>
        <clipPath id="femora-c"><circle cx="50" cy="50" r="44" /></clipPath>
      </defs>
      <circle cx="50" cy="50" r="44" fill="var(--f-surface-2)" />
      <g clipPath="url(#femora-c)"><path d="M0 58 C20 76 36 34 58 40 C76 46 80 26 100 18 L100 100 L0 100Z" fill="url(#femora-g)" /></g>
    </svg>
  );
}
