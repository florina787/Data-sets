import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function Card({ title, actions, children, className = "", subtitle }: { title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel p-4 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h3 className="text-sm font-semibold tracking-wide">{title}</h3>}
            {subtitle && <p className="muted mt-0.5 text-xs">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES: Record<string, string> = {
  teal: "bg-teal/15 text-teal border-teal/40",
  amber: "bg-amber/15 text-amber border-amber/40",
  red: "bg-blocked/15 text-blocked border-blocked/40",
  purple: "bg-purple/15 text-purple border-purple/40 dark:text-lavender",
  gold: "bg-gold/20 text-[#7a5d1c] border-gold/60 dark:text-gold",
  gray: "bg-black/5 dark:bg-white/10 muted border-token",
};

export function Badge({ children, tone = "gray", title }: { children: ReactNode; tone?: string; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-semibold ${TONES[tone] ?? TONES.gray}`}>
      {children}
    </span>
  );
}

export function statusTone(s: string): string {
  if (["ALLOW", "completed", "approved", "passed", "ok", "trusted", "current", "available", "simulated", "local"].includes(s)) return "teal";
  if (["DENY", "failed", "denied", "rejected", "blocked", "cancelled", "error", "expired"].includes(s)) return "red";
  if (["running", "queued", "retrying", "awaiting_approval", "pending", "needs_clarification", "completed_with_errors", "superseded", "not_detected", "planned", "not_connected"].includes(s)) return "amber";
  return "gray";
}

export function Kpi({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: string; hint?: string }) {
  const color = tone === "red" ? "text-blocked" : tone === "amber" ? "text-amber" : tone === "teal" ? "text-teal" : "";
  return (
    <div className="panel px-3 py-2.5" title={hint}>
      <div className="muted text-[11px] font-medium uppercase tracking-wider">{label}</div>
      <div className={`mt-0.5 text-xl font-bold tabular-nums ${color}`}>{value}</div>
      {hint && <div className="muted mt-0.5 text-[11px]">{hint}</div>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="muted flex items-center gap-2 p-6 text-sm">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}...
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-token p-8 text-center">
      <Inbox className="muted h-6 w-6" aria-hidden />
      <div className="text-sm font-semibold">{title}</div>
      {children && <div className="muted max-w-md text-xs">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const e = error as ApiError;
  const denied = e?.code === "policy_denied";
  const det = (e?.details ?? {}) as { policy_id?: string };
  return (
    <div role="alert" className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${denied ? "border-blocked/40 bg-blocked/10" : "border-amber/40 bg-amber/10"}`}>
      <AlertTriangle className={`mt-0.5 h-4 w-4 ${denied ? "text-blocked" : "text-amber"}`} aria-hidden />
      <div className="flex-1">
        <div className="font-semibold">{denied ? `Denied by policy ${det.policy_id ?? ""}` : "Something went wrong"}</div>
        <div className="muted mt-0.5">{e?.message ?? String(error)}</div>
        {e?.requestId && <div className="muted mt-1 text-[11px]">request_id {e.requestId}</div>}
      </div>
      {onRetry && (
        <button className="btn btn-ghost" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function Tabs({ tabs, active, onChange, label }: { tabs: { id: string; label: string }[]; active: string; onChange: (id: string) => void; label: string }) {
  return (
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1 border-b border-token pb-1">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${active === t.id ? "bg-purple text-white" : "muted hover:bg-[var(--panel-2)]"}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function PageHeader({ title, subtitle, icon, actions }: { title: string; subtitle?: string; icon?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="flex items-center gap-3">
        {icon && <div className="rounded-xl bg-purple/15 p-2 text-purple dark:text-lavender">{icon}</div>}
        <div>
          <h1 className="text-xl font-bold tracking-tight">{title}</h1>
          {subtitle && <p className="muted text-sm">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
