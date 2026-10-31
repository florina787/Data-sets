import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

export function Card({ title, actions, children, className = "", subtitle }: { title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            {title && <h3 className="text-sm font-semibold">{title}</h3>}
            {subtitle && <p className="muted mt-0.5 text-xs leading-relaxed">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

const TONES: Record<string, string> = {
  teal: "border-pos/30 bg-pos/10 text-pos",
  amber: "border-warn/30 bg-warn/10 text-warn",
  red: "border-neg/30 bg-neg/10 text-neg",
  purple: "border-indigo/30 bg-indigo/15 text-indigo dark:text-[#A5B4FC]",
  gold: "border-cyan/30 bg-cyan/10 text-[#0E7490] dark:text-cyan",
  violet: "border-violet/30 bg-violet/15 text-violet",
  gray: "border-token bg-white/5 muted",
};

export function Badge({ children, tone = "gray", title }: { children: ReactNode; tone?: string; title?: string }) {
  return (
    <span title={title} className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[11px] font-medium ${TONES[tone] ?? TONES.gray}`}>
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
  const color = tone === "red" ? "text-neg" : tone === "amber" ? "text-warn" : tone === "teal" ? "text-pos" : "";
  return (
    <div className="rounded-xl border border-token bg-white/[0.02] p-4" title={hint}>
      <p className="label">{label}</p>
      <p className={`num mt-1.5 text-2xl font-semibold tracking-tight ${color}`}>{value}</p>
      {hint && <p className="muted mt-1 text-xs">{hint}</p>}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="space-y-3 p-2">
      <div className="muted flex items-center gap-2 text-sm"><Loader2 className="h-4 w-4 animate-spin text-cyan" aria-hidden /> {label}...</div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div className={`relative overflow-hidden rounded-lg bg-white/5 ${className}`}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/5 to-transparent" />
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
    <div role="alert" className={`flex items-start gap-3 rounded-xl border p-4 text-sm ${denied ? "border-neg/30 bg-neg/10" : "border-warn/30 bg-warn/10"}`}>
      <AlertTriangle className={`mt-0.5 h-4 w-4 ${denied ? "text-neg" : "text-warn"}`} aria-hidden />
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
    <div role="tablist" aria-label={label} className="flex flex-wrap gap-1 border-b border-token pb-2">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={active === t.id}
          className={`rounded-xl px-3 py-1.5 text-sm ${active === t.id ? "border border-indigo/30 bg-indigo/15 text-[var(--text)]" : "muted border border-transparent hover:bg-white/[0.04] hover:text-[var(--text)]"}`}
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
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="flex items-center gap-3">
        {icon && <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-indigo/30 to-cyan/10 text-cyan ring-1 ring-[var(--border)]">{icon}</div>}
        <div>
          <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="muted mt-0.5 max-w-4xl text-sm">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}
