import { AlertTriangle, Loader2, Inbox } from "lucide-react";
import type { ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className, dark }: { children: ReactNode; className?: string; dark?: boolean }) {
  return (
    <section className={cx("rounded-2xl border p-5", dark ? "border-white/10 bg-white/[0.04] text-white" : "border-dome-100 bg-white/80 shadow-tile backdrop-blur", className)}>
      {children}
    </section>
  );
}

export function Eyebrow({ children, dark }: { children: ReactNode; dark?: boolean }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-medium tracking-wide",
      dark ? "border-white/15 bg-white/5 text-white/80" : "border-dome-100 bg-white text-ink-soft")}>
      <span className="h-1.5 w-1.5 rounded-full bg-dome-500" />
      {children}
    </span>
  );
}

export function SectionTitle({ eyebrow, title, sub, dark }: { eyebrow?: string; title: ReactNode; sub?: ReactNode; dark?: boolean }) {
  return (
    <header className="mb-5">
      {eyebrow && <Eyebrow dark={dark}>{eyebrow}</Eyebrow>}
      <h2 className={cx("mt-3 font-display text-2xl font-semibold tracking-tight", dark ? "text-white" : "text-ink")}>{title}</h2>
      {sub && <p className={cx("mt-1 max-w-3xl text-sm", dark ? "text-white/60" : "text-ink-soft")}>{sub}</p>}
    </header>
  );
}

type BtnKind = "primary" | "ghost" | "accent" | "danger";
export function Button({ kind = "primary", children, className, ...rest }: React.ButtonHTMLAttributes<HTMLButtonElement> & { kind?: BtnKind }) {
  const k: Record<BtnKind, string> = {
    primary: "bg-ink text-white hover:bg-ink/85",
    ghost: "bg-white text-ink border border-dome-100 hover:bg-dome-50",
    accent: "bg-dome-500 text-white hover:bg-dome-600",
    danger: "bg-bad text-white hover:bg-bad/85",
  };
  return (
    <button {...rest} className={cx("inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-dome-500", k[kind], className)}>
      {children}
    </button>
  );
}

const STATUS_STYLE: Record<string, string> = {
  confirmed: "bg-ok/10 text-ok border-ok/30",
  probable: "bg-dome-50 text-dome-700 border-dome-200",
  inconclusive: "bg-warn/10 text-warn border-warn/30",
  disproven: "bg-ink/5 text-ink-mute border-ink/10 line-through decoration-1",
  succeeded: "bg-ok/10 text-ok border-ok/30", resolved: "bg-ok/10 text-ok border-ok/30", healthy: "bg-ok/10 text-ok border-ok/30",
  verified: "bg-ok/10 text-ok border-ok/30", pass: "bg-ok/10 text-ok border-ok/30", success: "bg-ok/10 text-ok border-ok/30",
  approved: "bg-dome-50 text-dome-700 border-dome-200", pending_approval: "bg-warn/10 text-warn border-warn/30", pending: "bg-ink/5 text-ink-soft border-ink/10",
  executing: "bg-dome-50 text-dome-700 border-dome-200", remediating: "bg-dome-50 text-dome-700 border-dome-200", investigating: "bg-warn/10 text-warn border-warn/30",
  failed: "bg-bad/10 text-bad border-bad/30", fail: "bg-bad/10 text-bad border-bad/30", blocked: "bg-bad/10 text-bad border-bad/30", denied: "bg-bad/10 text-bad border-bad/30",
  rejected: "bg-bad/10 text-bad border-bad/30", open: "bg-bad/10 text-bad border-bad/30", degraded: "bg-warn/10 text-warn border-warn/30",
  unknown: "bg-ink/5 text-ink-mute border-ink/10", timed_out: "bg-bad/10 text-bad border-bad/30", warn: "bg-warn/10 text-warn border-warn/30",
  simulated: "bg-dome-50 text-dome-700 border-dome-200", implemented: "bg-warn/10 text-warn border-warn/30", not_implemented: "bg-ink/5 text-ink-mute border-ink/10",
};

export function Badge({ value, label }: { value: string; label?: string }) {
  return (
    <span className={cx("inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize", STATUS_STYLE[value] ?? "bg-ink/5 text-ink-soft border-ink/10")}>
      {label ?? value.replace(/_/g, " ")}
    </span>
  );
}

export function Stat({ label, value, sub, dark }: { label: string; value: ReactNode; sub?: ReactNode; dark?: boolean }) {
  return (
    <div>
      <div className={cx("text-[11px] uppercase tracking-[0.14em]", dark ? "text-white/50" : "text-ink-mute")}>{label}</div>
      <div className={cx("mt-1 font-display text-3xl font-semibold tabular-nums", dark ? "text-white" : "text-ink")}>{value}</div>
      {sub && <div className={cx("mt-0.5 text-xs", dark ? "text-white/50" : "text-ink-soft")}>{sub}</div>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-ink-soft">
      <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" /> {label}…
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-bad/30 bg-bad/5 p-4 text-sm text-bad">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">{error}</div>
      {onRetry && <button onClick={onRetry} className="underline">Retry</button>}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-sm text-ink-mute">
      <Inbox className="h-5 w-5" />
      {children}
    </div>
  );
}

export function DemoLabel({ className }: { className?: string }) {
  return <span className={cx("rounded-md bg-ember/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ember", className)}>Synthetic demo data</span>;
}
